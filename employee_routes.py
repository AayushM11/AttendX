# import sys, os
# sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))  

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from database import get_db
from models import Employee, Department

router = APIRouter()

@router.get("/api/employees")
async def list_employees(db: Session = Depends(get_db)):
    employees = db.query(Employee).filter(Employee.is_active == True).all()
    return[
        {
            "id":emp.id,
            "employee_id":emp.employee_id,
            "name": emp.full_name,
            "email": emp.email,
            "department": emp.department.name if emp.department else None,
            "designation" :emp.designation,
            "profile_image": emp.profile_image
        }
        for emp in employees
    ]

@router.get("/api/departments")
async def list_departments(db:Session = Depends(get_db)):
    department = db.query(Department).all()
    return [{"id": d.id, "name": d.name} for d in department]

