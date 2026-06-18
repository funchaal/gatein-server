from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.dependencies import get_company_from_api_key
from app.models import Company, Driver, Trip, TripLayout

router = APIRouter()

# --- SCHEMAS (Pydantic) ---

class DriverSchema(BaseModel):
    tax_id: str = Field(..., description="CPF ou CNPJ do motorista (Apenas números)")
    license_number: Optional[str] = Field(None, description="Número da CNH")
    license_category: Optional[str] = Field(None, description="Categoria da CNH (ex: E)")

class TripBaseSchema(BaseModel):
    ref: str = Field(..., description="Referência única da viagem")
    layout_ref: Optional[str] = Field(None, description="Referência do layout a ser utilizado")
    vehicle_plate: Optional[str] = Field(None, description="Placa do veículo")
    summary: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    custom_data: Optional[Dict[str, Any]] = Field(default_factory=dict)

class CreateTripPayload(BaseModel):
    driver: DriverSchema
    trip: TripBaseSchema

class UpdateTripPayload(BaseModel):
    ref: str = Field(..., description="Referência da viagem que será atualizada")
    trip: Dict[str, Any] = Field(..., description="Campos a atualizar")


# --- ROTAS ---

@router.post("/trips", status_code=201)
def create_trips(
    items: List[CreateTripPayload],
    db: Session = Depends(get_db),
    company: Company = Depends(get_company_from_api_key)
):
    if not items:
        raise HTTPException(status_code=400, detail={"code": "EMPTY_PAYLOAD"})

    # Validação de Duplicidade (Fail-Fast)
    incoming_refs = [item.trip.ref for item in items]
    existing = db.query(Trip.ref).filter(
        Trip.trucking_company_id == company.id,
        Trip.ref.in_(incoming_refs)
    ).all()

    if existing:
        existing_refs = [e[0] for e in existing]
        raise HTTPException(
            status_code=409, 
            detail={"code": "DUPLICATE_KEY", "conflicting_refs": existing_refs}
        )

    # Validação de Trip Layouts (Fail-Fast)
    incoming_layout_refs = {item.trip.layout_ref for item in items if item.trip.layout_ref}
    if incoming_layout_refs:
        existing_layouts = db.query(TripLayout.ref).filter(
            TripLayout.trucking_company_id == company.id,
            TripLayout.ref.in_(incoming_layout_refs)
        ).all()
        
        existing_layout_refs = {e[0] for e in existing_layouts}
        missing_layouts = incoming_layout_refs - existing_layout_refs
        
        if missing_layouts:
            raise HTTPException(
                status_code=400, 
                detail={"code": "INVALID_LAYOUT_REF", "missing_layouts": list(missing_layouts)}
            )

    created_refs = []

    for item in items:
        # Processamento do Motorista
        driver = db.query(Driver).filter_by(tax_id=item.driver.tax_id).first()
        if not driver:
            driver = Driver(
                tax_id=item.driver.tax_id,
                driver_license_number=item.driver.license_number,
                driver_license_category=item.driver.license_category,
                validated_by=company.id
            )
            db.add(driver)
            db.flush() 
        else:
            if item.driver.license_number and driver.driver_license_number != item.driver.license_number:
                driver.driver_license_number = item.driver.license_number
            else:
                driver.updated_at = datetime.utcnow()
            driver.validated_by = company.id

        # Processamento da Viagem (Trip)
        new_trip = Trip(
            trucking_company_id=company.id,
            driver_id=driver.id,
            ref=item.trip.ref,
            layout_ref=item.trip.layout_ref,
            vehicle_plate=item.trip.vehicle_plate,
            summary=item.trip.summary,
            start_time=item.trip.start_time,
            end_time=item.trip.end_time,
            custom_data=item.trip.custom_data,
        )
        db.add(new_trip)
        created_refs.append(new_trip.ref)

    try:
        db.commit()
        return {"success": True, "data": {"created_refs": created_refs, "status": "created"}}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail={"code": "INTERNAL_ERROR", "message": str(e)})


@router.put("/trips")
def update_trips(
    items: List[UpdateTripPayload],
    db: Session = Depends(get_db),
    company: Company = Depends(get_company_from_api_key)
):
    if not items:
        raise HTTPException(status_code=400, detail={"code": "EMPTY_PAYLOAD"})

    incoming_refs = [item.ref for item in items]
    
    trips = db.query(Trip).filter(
        Trip.trucking_company_id == company.id,
        Trip.ref.in_(incoming_refs)
    ).all()
    
    trip_map = {t.ref: t for t in trips}
    protected_fields = {"id", "trucking_company_id", "ref", "driver_id"}
    updated_refs = []
    not_found_refs = []

    for item in items:
        if item.ref not in trip_map:
            not_found_refs.append(item.ref)
            continue
        
        trip_obj = trip_map[item.ref]
        
        for key, value in item.trip.items():
            if key not in protected_fields and hasattr(trip_obj, key):
                setattr(trip_obj, key, value)
        
        updated_refs.append(item.ref)

    if not_found_refs:
        db.rollback() 
        raise HTTPException(
            status_code=404, 
            detail={"code": "REFS_NOT_FOUND", "missing_refs": not_found_refs}
        )

    try:
        db.commit()
        return {"success": True, "data": {"updated_refs": updated_refs, "status": "updated"}}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail={"code": "INTERNAL_ERROR", "message": str(e)})


@router.delete("/trips")
def delete_trips(
    refs: List[str],
    db: Session = Depends(get_db),
    company: Company = Depends(get_company_from_api_key)
):
    if not refs:
        raise HTTPException(status_code=400, detail={"code": "EMPTY_PAYLOAD"})

    affected_rows = db.query(Trip).filter(
        Trip.trucking_company_id == company.id,
        Trip.ref.in_(refs)
    ).update({"status": "DELETED"}, synchronize_session=False)
    
    if not affected_rows:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND"})

    db.commit()
    return {"success": True, "data": {"deleted_count": affected_rows, "status": "deleted"}}