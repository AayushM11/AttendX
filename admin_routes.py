import os
import shutil
import hashlib
import datetime
import uuid

from fastapi import APIRouter, Depends, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from database import get_db
from models import Admin, Employee, Department, Attendance, LeaveRequest, Holiday, FaceEmbedding
from recognition import generate_embeddings_for_employee

from geofence import get_company_settings

router = APIRouter()

# Absolute path to templates folder — works regardless of where uvicorn is run from
TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def get_admin_or_redirect(request: Request):
    return request.session.get("admin_id")


#  Auth 

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("admin/login.html", {"request": request})


@router.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    admin = db.query(Admin).filter(Admin.username == username).first()
    if not admin or admin.password_hash != hash_password(password):
        return templates.TemplateResponse("admin/login.html", {
            "request": request, "error": "Invalid credentials"
        })
    request.session["admin_id"] = admin.id
    request.session["admin_name"] = admin.username
    return RedirectResponse(url="/admin/dashboard", status_code=302)


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)


#  Dashboard 

@router.get("/admin/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    if not get_admin_or_redirect(request):
        return RedirectResponse("/login")

    today = datetime.date.today()
    total_employees = db.query(Employee).filter(Employee.is_active == True).count()
    present_today = db.query(Attendance).filter(Attendance.date == today).count()
    absent_today = total_employees - present_today
    pending_leaves = db.query(LeaveRequest).filter(LeaveRequest.status == "pending").count()
    self_registered = db.query(Employee).filter(Employee.self_registered == True, Employee.is_active == True).count()

    trend = []
    for i in range(6, -1, -1):
        d = today - datetime.timedelta(days=i)
        cnt = db.query(Attendance).filter(Attendance.date == d).count()
        trend.append({"date": d.strftime("%a"), "count": cnt})

    dept_stats = db.query(
        Department.name, func.count(Attendance.id)
    ).join(Employee, Employee.department_id == Department.id)\
     .join(Attendance, and_(Attendance.employee_id == Employee.id, Attendance.date == today))\
     .group_by(Department.name).all()

    recent_attendance = db.query(Attendance).filter(
        Attendance.date == today
    ).order_by(Attendance.check_in.desc()).limit(10).all()

    return templates.TemplateResponse("admin/dashboard.html", {
        "request": request,
        "total_employees": total_employees,
        "present_today": present_today,
        "absent_today": absent_today,
        "pending_leaves": pending_leaves,
        "trend": trend,
        "dept_stats": dept_stats,
        "recent_attendance": recent_attendance,
        "today": today.strftime("%A, %d %B %Y"),
        "admin_name": request.session.get("admin_name", "Admin"),
        "self_registered": self_registered
    })


#  Employees 

@router.get("/admin/employees", response_class=HTMLResponse)
async def employee_list(request: Request, db: Session = Depends(get_db)):
    if not get_admin_or_redirect(request):
        return RedirectResponse("/login")
    employees = db.query(Employee).filter(Employee.is_active == True).all()
    departments = db.query(Department).all()
    return templates.TemplateResponse("admin/employees.html", {
        "request": request, "employees": employees, "departments": departments
    })


@router.get("/admin/employees/register", response_class=HTMLResponse)
async def register_page(request: Request, db: Session = Depends(get_db)):
    if not get_admin_or_redirect(request):
        return RedirectResponse("/login")
    departments = db.query(Department).all()
    return templates.TemplateResponse("admin/register_employee.html", {
        "request": request, "departments": departments
    })


@router.post("/admin/employees/register")
async def register_employee(
    request: Request,
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(None),
    department_id: int = Form(...),
    designation: str = Form(...),
    date_of_joining: str = Form(...),
    face_photos: list[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    departments = db.query(Department).all()

    #  Duplicate checks 
    if db.query(Employee).filter(Employee.email == email).first():
        return templates.TemplateResponse("admin/register_employee.html", {
            "request": request,
            "departments": departments,
            "error": f"An employee with email '{email}' is already registered.",
            "form_data": {"first_name": first_name, "last_name": last_name,
                          "email": email, "phone": phone, "designation": designation,
                          "date_of_joining": date_of_joining}
        })

    full_name_check = db.query(Employee).filter(
        Employee.first_name == first_name,
        Employee.last_name == last_name,
        Employee.is_active == True
    ).first()
    if full_name_check:
        return templates.TemplateResponse("admin/register_employee.html", {
            "request": request,
            "departments": departments,
            "error": f"An employee named '{first_name} {last_name}' already exists. Use a different name or check the employee list.",
            "form_data": {"first_name": first_name, "last_name": last_name,
                          "email": email, "phone": phone, "designation": designation,
                          "date_of_joining": date_of_joining}
        })

    #  Generate employee ID 
    emp_count = db.query(Employee).count() + 1
    employee_id = f"EMP{emp_count:04d}"

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    upload_dir = os.path.join(base_dir, "uploaded_images", employee_id)
    os.makedirs(upload_dir, exist_ok=True)

    #  Save all face photos
    image_path = None
    saved_count = 0
    valid_photos = [p for p in (face_photos or []) if p and p.filename]

    for i, photo in enumerate(valid_photos):
        ext = photo.filename.rsplit(".", 1)[-1].lower()
        filename = f"face_{i+1:02d}.{ext}"
        path = os.path.join(upload_dir, filename)
        with open(path, "wb") as f:
            shutil.copyfileobj(photo.file, f)
        if i == 0:
            image_path = f"uploaded_images/{employee_id}/{filename}"
        saved_count += 1

    #  Create employee record 
    emp = Employee(
        employee_id=employee_id,
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=phone,
        department_id=department_id,
        designation=designation,
        date_of_joining=datetime.date.fromisoformat(date_of_joining),
        profile_image=image_path
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)

    #  Generate face embeddings 
    if saved_count > 0:
        generate_embeddings_for_employee(emp.id, db)

    return RedirectResponse(url=f"/admin/employees/{emp.id}", status_code=302)


@router.get("/admin/employees/{emp_id}", response_class=HTMLResponse)
async def employee_profile(emp_id: int, request: Request, db: Session = Depends(get_db)):
    if not get_admin_or_redirect(request):
        return RedirectResponse("/login")
    employee = db.query(Employee).filter(Employee.id == emp_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Not found")

    today = datetime.date.today()
    month_start = today.replace(day=1)
    attendance = db.query(Attendance).filter(
        and_(Attendance.employee_id == emp_id, Attendance.date >= month_start)
    ).order_by(Attendance.date.desc()).all()

    present = sum(1 for a in attendance if a.status == "present")
    embeddings_count = db.query(FaceEmbedding).filter(FaceEmbedding.employee_id == emp_id).count()

    departments = db.query(Department).all()
    return templates.TemplateResponse("admin/employee_profile.html", {
        "request": request,
        "employee": employee,
        "attendance": attendance,
        "present_days": present,
        "embeddings_count": embeddings_count,
        "departments": departments
    })


@router.post("/admin/employees/{emp_id}/upload-images")
async def upload_face_images(
    emp_id: int,
    images: list[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    employee = db.query(Employee).filter(Employee.id == emp_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Not found")

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    upload_dir = os.path.join(base_dir, "uploaded_images", employee.employee_id)
    os.makedirs(upload_dir, exist_ok=True)

    for img in images:
        if img.filename:
            ext = img.filename.split(".")[-1]
            with open(os.path.join(upload_dir, f"{uuid.uuid4()}.{ext}"), "wb") as f:
                shutil.copyfileobj(img.file, f)

    result = generate_embeddings_for_employee(emp_id, db)
    return JSONResponse(result)


@router.post("/admin/employees/{emp_id}/generate-encodings")
async def generate_encodings(emp_id: int, db: Session = Depends(get_db)):
    return JSONResponse(generate_embeddings_for_employee(emp_id, db))


@router.post("/admin/employees/{emp_id}/edit")
async def edit_employee(
    emp_id: int,
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(None),
    department_id: str = Form(None),
    designation: str = Form(None),
    db: Session = Depends(get_db)
):
    employee = db.query(Employee).filter(Employee.id == emp_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Not found")
    employee.first_name = first_name
    employee.last_name = last_name
    employee.email = email
    employee.phone = phone
    employee.department_id = int(department_id) if department_id and department_id.strip() else None
    employee.designation = designation
    db.commit()
    return RedirectResponse(url=f"/admin/employees/{emp_id}", status_code=302)


@router.post("/admin/employees/{emp_id}/delete")
async def delete_employee(emp_id: int, db: Session = Depends(get_db)):
    employee = db.query(Employee).filter(Employee.id == emp_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Not found")
    employee.is_active = False
    db.commit()
    return RedirectResponse(url="/admin/employees", status_code=302)


#  Attendance

@router.get("/admin/attendance", response_class=HTMLResponse)
async def attendance_page(request: Request, db: Session = Depends(get_db)):
    if not get_admin_or_redirect(request):
        return RedirectResponse("/login")
    
    import datetime

    date_str = request.query_params.get("date")
    if date_str:
        try:
            target = datetime.date.fromisoformat(date_str)
        except ValueError:
            target = datetime.date.today()
    else:
        target = datetime.date.today()

    records = db.query(Attendance).filter(
        Attendance.date == target
    ).order_by(Attendance.check_in.desc()).all()
   
    total = db.query(Employee).filter(Employee.is_active == True).count()
    return templates.TemplateResponse("admin/attendance.html", {
        "request": request,
        "records": records,
        "today": target,
        "total": total,
        "present": len(records),
        "absent": total - len(records),
        "admin_name": request.session.get("admin_name", "Admin"),
    })


#  Leaves 
@router.get("/admin/leaves", response_class=HTMLResponse)
async def leaves_page(request: Request, db: Session = Depends(get_db)):
    if not get_admin_or_redirect(request):
        return RedirectResponse("/login")
    leaves = db.query(LeaveRequest).order_by(LeaveRequest.applied_at.desc()).all()
    return templates.TemplateResponse("admin/leaves.html", {
        "request": request, "leaves": leaves
    })


@router.post("/admin/leaves/{leave_id}/action")
async def leave_action(
    leave_id: int,
    action: str = Form(...),
    comment: str = Form(""),
    db: Session = Depends(get_db)
):
    leave = db.query(LeaveRequest).filter(LeaveRequest.id == leave_id).first()
    if not leave:
        raise HTTPException(status_code=404, detail="Not found")
    leave.status = action
    leave.admin_comment = comment
    leave.reviewed_at = datetime.datetime.now()
    db.commit()
    return RedirectResponse(url="/admin/leaves", status_code=302)


#  Holidays 

@router.get("/admin/holidays", response_class=HTMLResponse)
async def holidays_page(request: Request, db: Session = Depends(get_db)):
    if not get_admin_or_redirect(request):
        return RedirectResponse("/login")
    holidays = db.query(Holiday).order_by(Holiday.date).all()
    return templates.TemplateResponse("admin/holidays.html", {
        "request": request, "holidays": holidays
    })


@router.post("/admin/holidays/add")
async def add_holiday_form(
    name: str = Form(...),
    date: str = Form(...),
    description: str = Form(""),
    db: Session = Depends(get_db)
):
    db.add(Holiday(name=name, date=datetime.date.fromisoformat(date), description=description))
    db.commit()
    return RedirectResponse(url="/admin/holidays", status_code=302)


@router.post("/admin/holidays/{hid}/delete")
async def delete_holiday_form(hid: int, db: Session = Depends(get_db)):
    h = db.query(Holiday).filter(Holiday.id == hid).first()
    if h:
        db.delete(h)
        db.commit()
    return RedirectResponse(url="/admin/holidays", status_code=302)

#GeoFence settings

@router.get("/admin/geofence", response_class=HTMLResponse)
async def geofence_settings(request: Request, db: Session = Depends(get_db)):
    if not get_admin_or_redirect(request):
        return RedirectResponse("/login")
    
    import datetime
    today = datetime.date.today()
    settings = get_company_settings(db)

    #count today's verified attendance
    attendance_today = db.query(Attendance).filter(
        Attendance.date == today
    ).count()

    return templates.TemplateResponse("admin/geo_settings.html", {
        "request": request,
        "settings": settings,
        "attendance_today": attendance_today,
        "admin_name": request.session.get("admin_name","Admin"),
        })


#  Departments 

@router.get("/admin/geofence", response_class=HTMLResponse)
async def geofence_page(request: Request, db: Session = Depends(get_db)):
    if not get_admin_or_redirect(request):
        return RedirectResponse("/login")
 
    import datetime
    today    = datetime.date.today()
    
    try:
        settings = get_company_settings(db)
    except Exception as e:
        print(f"[Geofence] Settings load error: {e}")
        # Default settings if table doesn't exist yet
        settings = {
            "lat":      22.55630805480531,
            "lng":      72.95262732498357,
            "radius_m": 100.0,
            "enabled":  True,
            "name":     "Company HQ",
        }
 
    try:
        attendance_today = db.query(Attendance).filter(
            Attendance.date == today
        ).count()
    except Exception:
        attendance_today = 0
 
    return templates.TemplateResponse("admin/geo_settings.html", {
        "request":          request,
        "settings":         settings,
        "attendance_today": attendance_today,
        "admin_name":       request.session.get("admin_name", "Admin"),
    })

