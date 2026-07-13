import json
from typing import List, Optional, Dict, Any, Union
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.core.dependencies import get_company_from_api_key
from app.models import Company, Driver, Trip, TripLayout, TripLog

router = APIRouter()

# --- HELPER LOGS ---
def create_trip_log(db: Session, company_id: Any, trip_id: Any, event: str, message: str, data: dict):
    """
    Utility function to log changes and events for a trip in the database.
    Serializes date/time elements dynamically to JSON format.
    """
    def json_serializer(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Type {type(obj)} not serializable")
        
    serialized_data = json.loads(json.dumps(data, default=json_serializer))
    
    log = TripLog(
        company_id=company_id,
        trip_id=trip_id,
        event=event,
        message=message,
        json=serialized_data
    )
    db.add(log)


# --- SCHEMAS (Pydantic Request/Response) ---

class DriverSchema(BaseModel):
    """Schema representing driver profile details."""
    tax_id: str = Field(..., description="CPF ou CNPJ do motorista (Apenas números)")
    driver_license_number: str = Field(..., description="Número da CNH")
    license_category: str = Field(..., description="Categoria da CNH (ex: E)")

class TripBaseSchema(BaseModel):
    """Schema representing core parameters of a trip, including all location metrics."""
    ref: str = Field(..., description="Referência única da viagem")
    layout_ref: str = Field(..., description="Referência do layout a ser utilizado")
    vehicle_plate: Optional[str] = Field(None, description="Placa do veículo")
    summary: Optional[str] = Field(None, description="Resumo ou observações sobre a viagem")
    start_time: Optional[datetime] = Field(None, description="Data/hora prevista de início")
    end_time: Optional[datetime] = Field(None, description="Data/hora prevista de término")
    schedule_start_tolerance: int = Field(0, description="Tolerância de início em minutos")
    schedule_end_tolerance: int = Field(0, description="Tolerância de término em minutos")
    custom_data: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Dados customizados estruturados")
    
    # Location/Address Details (Origin)
    origin_street: Optional[str] = Field(None, description="Rua de origem")
    origin_number: Optional[str] = Field(None, description="Número do endereço de origem")
    origin_city: Optional[str] = Field(None, description="Cidade de origem")
    origin_state: Optional[str] = Field(None, description="Estado de origem")
    origin_country: Optional[str] = Field(None, description="País de origem")
    origin_zip: Optional[str] = Field(None, description="CEP de origem")
    origin_lat: Optional[float] = Field(None, description="Latitude de origem")
    origin_lng: Optional[float] = Field(None, description="Longitude de origem")
    
    # Location/Address Details (Destiny)
    destiny_street: Optional[str] = Field(None, description="Rua de destino")
    destiny_number: Optional[str] = Field(None, description="Número do endereço de destino")
    destiny_city: Optional[str] = Field(None, description="Cidade de destino")
    destiny_state: Optional[str] = Field(None, description="Estado de destino")
    destiny_country: Optional[str] = Field(None, description="País de destino")
    destiny_zip: Optional[str] = Field(None, description="CEP de destino")
    destiny_lat: Optional[float] = Field(None, description="Latitude de destino")
    destiny_lng: Optional[float] = Field(None, description="Longitude de destino")
    
    # General descriptive location labels
    from_location: Optional[str] = Field(None, description="Descrição do local de partida (ex: Filial A)")
    to_location: Optional[str] = Field(None, description="Descrição do local de chegada (ex: Porto Seco B)")

class CreateTripPayload(BaseModel):
    """Payload to create a trip containing driver and trip details."""
    driver: DriverSchema
    trip: TripBaseSchema

class UpdateTripPayload(BaseModel):
    """Payload to partially update an existing trip."""
    ref: str = Field(..., description="Referência da viagem que será atualizada")
    trip: Dict[str, Any] = Field(..., description="Campos a atualizar")

# Response Schemas

class CreateTripsResponseData(BaseModel):
    created_refs: List[str]
    status: str

class CreateTripsResponse(BaseModel):
    success: bool = True
    data: CreateTripsResponseData

class UpdateTripsResponseData(BaseModel):
    updated_refs: List[str]
    status: str

class UpdateTripsResponse(BaseModel):
    success: bool = True
    data: UpdateTripsResponseData

class DeleteTripsResponseData(BaseModel):
    deleted_count: int
    status: str

class DeleteTripsResponse(BaseModel):
    success: bool = True
    data: DeleteTripsResponseData

class TripLogResponseItem(BaseModel):
    """Item schema representing a log trace of a trip."""
    id: str
    event: str
    message: str
    json_data: Optional[Dict[str, Any]] = Field(None, validation_alias="json", serialization_alias="json")
    created_at: Optional[str] = None

class TripDataResponseItem(BaseModel):
    """Item schema representing deep details of a trip."""
    id: str
    trucking_company_id: str
    ref: str
    layout_ref: Optional[str] = None
    driver_id: Optional[str] = None
    vehicle_plate: Optional[str] = None
    status: str
    summary: Optional[str] = None
    schedule_start_time: Optional[str] = None
    schedule_end_time: Optional[str] = None
    schedule_start_tolerance: int
    schedule_end_tolerance: int
    custom_data: Optional[Dict[str, Any]] = None
    
    # Location/Address details (Origin)
    origin_street: Optional[str] = None
    origin_number: Optional[str] = None
    origin_city: Optional[str] = None
    origin_state: Optional[str] = None
    origin_country: Optional[str] = None
    origin_zip: Optional[str] = None
    origin_lat: Optional[float] = None
    origin_lng: Optional[float] = None
    
    # Location/Address details (Destiny)
    destiny_street: Optional[str] = None
    destiny_number: Optional[str] = None
    destiny_city: Optional[str] = None
    destiny_state: Optional[str] = None
    destiny_country: Optional[str] = None
    destiny_zip: Optional[str] = None
    destiny_lat: Optional[float] = None
    destiny_lng: Optional[float] = None
    
    from_location: Optional[str] = None
    to_location: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class DriverLogResponseItem(BaseModel):
    """Schema representing driver profile details associated with the log search."""
    tax_id: str
    driver_license_number: Optional[str] = None
    driver_license_category: Optional[str] = None

class TripLogDataContent(BaseModel):
    """Nested container holding trip details, driver profile, and historical logs."""
    trip: TripDataResponseItem
    driver: Optional[DriverLogResponseItem] = None
    logs: List[TripLogResponseItem]

class TripLogQueryResult(BaseModel):
    """Item schema mapping query response including availability state and logs."""
    ref: str
    found: bool
    data: Optional[TripLogDataContent] = None

class TripLogsResponse(BaseModel):
    success: bool = True
    data: List[TripLogQueryResult]


# --- ROTAS ---

@router.post(
    "/trips", 
    status_code=201,
    response_model=CreateTripsResponse,
    summary="Criar Viagem(ns)",
    description="Registra uma única viagem ou uma lista de viagens juntamente com os perfis dos motoristas escalados para realizar o frete. Aceita tanto um objeto individual quanto um array (lote) de objetos. Realiza validações Fail-Fast."
)
def create_trips(
    payload: Union[CreateTripPayload, List[CreateTripPayload]],
    db: Session = Depends(get_db),
    company: Company = Depends(get_company_from_api_key)
):
    """
    Processes and registers new trips (single or batch).
    Validates layout references and references uniqueness before database insertion.
    """
    items = payload if isinstance(payload, list) else [payload]
    if not items:
        raise HTTPException(
            status_code=400, 
            detail={
                "code": "EMPTY_PAYLOAD",
                "message": "A lista de viagens enviada está vazia.",
                "suggestion": "Envie um array JSON contendo pelo menos um objeto com 'driver' e 'trip'."
            }
        )

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
            detail={
                "code": "DUPLICATE_KEY", 
                "message": "Uma ou mais viagens já existem com as referências enviadas.",
                "conflicting_refs": existing_refs
            }
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
                detail={
                    "code": "INVALID_LAYOUT_REF", 
                    "message": "Um ou mais layouts de viagem não existem no sistema.",
                    "missing_layouts": list(missing_layouts)
                }
            )

    # --- OPTIMIZATION: BATCH DRIVERS QUERY ---
    incoming_driver_tax_ids = {item.driver.tax_id for item in items}
    existing_drivers = db.query(Driver).filter(Driver.tax_id.in_(incoming_driver_tax_ids)).all()
    driver_map = {d.tax_id: d for d in existing_drivers}

    created_refs = []

    for item in items:
        # Process and retrieve Driver using pre-queried dictionary cache
        driver = driver_map.get(item.driver.tax_id)
        if not driver:
            driver = Driver(
                tax_id=item.driver.tax_id,
                driver_license_number=item.driver.driver_license_number,
                driver_license_category=item.driver.license_category,
                validated_by=company.id
            )
            db.add(driver)
            db.flush() 
            driver_map[item.driver.tax_id] = driver
        else:
            if item.driver.driver_license_number and driver.driver_license_number != item.driver.driver_license_number:
                driver.driver_license_number = item.driver.driver_license_number
            else:
                driver.updated_at = datetime.utcnow()
            driver.validated_by = company.id

        # Process and link Trip, populating all location fields
        new_trip = Trip(
            trucking_company_id=company.id,
            driver_id=driver.id,
            ref=item.trip.ref,
            layout_ref=item.trip.layout_ref,
            vehicle_plate=item.trip.vehicle_plate,
            summary=item.trip.summary,
            schedule_start_time=item.trip.start_time,
            schedule_end_time=item.trip.end_time,
            schedule_start_tolerance=item.trip.schedule_start_tolerance,
            schedule_end_tolerance=item.trip.schedule_end_tolerance,
            custom_data=item.trip.custom_data,
            
            # Origin fields
            origin_street=item.trip.origin_street,
            origin_number=item.trip.origin_number,
            origin_city=item.trip.origin_city,
            origin_state=item.trip.origin_state,
            origin_country=item.trip.origin_country,
            origin_zip=item.trip.origin_zip,
            origin_lat=item.trip.origin_lat,
            origin_lng=item.trip.origin_lng,
            
            # Destiny fields
            destiny_street=item.trip.destiny_street,
            destiny_number=item.trip.destiny_number,
            destiny_city=item.trip.destiny_city,
            destiny_state=item.trip.destiny_state,
            destiny_country=item.trip.destiny_country,
            destiny_zip=item.trip.destiny_zip,
            destiny_lat=item.trip.destiny_lat,
            destiny_lng=item.trip.destiny_lng,
            
            from_location=item.trip.from_location,
            to_location=item.trip.to_location,
        )
        db.add(new_trip)
        db.flush()
        
        create_trip_log(
            db=db,
            company_id=company.id,
            trip_id=new_trip.id,
            event="created",
            message="Viagem criada via API.",
            data={
                "ref": new_trip.ref,
                "vehicle_plate": new_trip.vehicle_plate,
                "start_time": new_trip.schedule_start_time.isoformat() if new_trip.schedule_start_time else None,
                "end_time": new_trip.schedule_end_time.isoformat() if new_trip.schedule_end_time else None,
            }
        )
        created_refs.append(new_trip.ref)

    try:
        db.commit()
        return {"success": True, "data": {"created_refs": created_refs, "status": "created"}}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, 
            detail={"code": "INTERNAL_ERROR", "message": "Erro ao salvar as viagens no banco de dados.", "error_details": str(e)}
        )


@router.put(
    "/trips",
    response_model=UpdateTripsResponse,
    summary="Atualizar Viagem(ns)",
    description="Atualiza campos de dados ou horários para viagens existentes mapeadas por suas referências. Aceita tanto um objeto individual quanto um array (lote) de objetos. Apenas campos não protegidos podem ser atualizados."
)
def update_trips(
    payload: Union[UpdateTripPayload, List[UpdateTripPayload]],
    db: Session = Depends(get_db),
    company: Company = Depends(get_company_from_api_key)
):
    """
    Partially updates metadata and location details of existing trips (single or batch).
    Performs validation ensuring all supplied references already exist in company context.
    """
    items = payload if isinstance(payload, list) else [payload]
    if not items:
        raise HTTPException(
            status_code=400, 
            detail={
                "code": "EMPTY_PAYLOAD", 
                "message": "A lista de atualizações enviada está vazia."
            }
        )

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
        
        db.flush()
        create_trip_log(
            db=db,
            company_id=company.id,
            trip_id=trip_obj.id,
            event="updated",
            message="Viagem atualizada via API.",
            data=item.trip
        )
        
        updated_refs.append(item.ref)

    if not_found_refs:
        db.rollback() 
        raise HTTPException(
            status_code=404, 
            detail={
                "code": "REFS_NOT_FOUND", 
                "message": "Uma ou mais referências de viagens não foram encontradas.",
                "missing_refs": not_found_refs
            }
        )

    try:
        db.commit()
        return {"success": True, "data": {"updated_refs": updated_refs, "status": "updated"}}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, 
            detail={"code": "INTERNAL_ERROR", "message": "Erro ao atualizar viagens.", "error_details": str(e)}
        )


@router.delete(
    "/trips",
    response_model=DeleteTripsResponse,
    summary="Excluir/Cancelar Viagem(ns)",
    description="Marca viagens existentes como DELETED (canceladas) no banco de dados. Aceita tanto uma única string de referência quanto um array (lote) de strings."
)
def delete_trips(
    payload: Union[str, List[str]],
    db: Session = Depends(get_db),
    company: Company = Depends(get_company_from_api_key)
):
    """
    Cancels or soft-deletes trips (single or batch). Sets status to DELETED and writes log records.
    """
    refs = payload if isinstance(payload, list) else [payload]
    if not refs:
        raise HTTPException(
            status_code=400, 
            detail={
                "code": "EMPTY_PAYLOAD", 
                "message": "A lista de referências de viagens enviada está vazia."
            }
        )

    trips = db.query(Trip).filter(
        Trip.trucking_company_id == company.id,
        Trip.ref.in_(refs)
    ).all()
    
    if not trips:
        raise HTTPException(
            status_code=404, 
            detail={
                "code": "NOT_FOUND", 
                "message": "Nenhuma viagem ativa encontrada para as referências informadas."
            }
        )

    for trip_obj in trips:
        trip_obj.status = "DELETED"
        create_trip_log(
            db=db,
            company_id=company.id,
            trip_id=trip_obj.id,
            event="deleted",
            message="Viagem deletada/cancelada.",
            data={"ref": trip_obj.ref, "status": "DELETED"}
        )

    db.commit()
    return {"success": True, "data": {"deleted_count": len(trips), "status": "deleted"}}


@router.get(
    "/trips/logs",
    response_model=TripLogsResponse,
    summary="Consultar Logs e Detalhes de Viagens",
    description="Fornece o status em tempo real das viagens juntamente com a trilha de auditoria e logs históricos detalhados."
)
def get_trips_logs(
    refs: List[str] = Query(..., description="Lista de referências de viagens"),
    db: Session = Depends(get_db),
    company: Company = Depends(get_company_from_api_key)
):
    """
    Fetches trip database information along with their execution log traces.
    """
    if not refs:
        raise HTTPException(
            status_code=400,
            detail={"code": "EMPTY_PAYLOAD", "message": "A lista de referências (refs) não pode estar vazia."}
        )

    # Fetch corresponding trips in batch
    trips = db.query(Trip).filter(
        Trip.trucking_company_id == company.id,
        Trip.ref.in_(refs)
    ).all()

    trip_map = {t.ref: t for t in trips}

    # Optimization: Batch query drivers to prevent N+1 queries
    driver_ids = [t.driver_id for t in trips if t.driver_id]
    drivers = db.query(Driver).filter(Driver.id.in_(driver_ids)).all() if driver_ids else []
    driver_map = {d.id: d for d in drivers}

    result = []
    for ref in refs:
        trip_obj = trip_map.get(ref)
        if not trip_obj:
            result.append({
                "ref": ref,
                "found": False,
                "data": None
            })
            continue

        # Fetch logs for each matching trip
        logs = db.query(TripLog).filter(
            TripLog.trip_id == trip_obj.id,
            TripLog.company_id == company.id
        ).order_by(TripLog.created_at.desc()).all()

        serialized_logs = [
            {
                "id": str(log.id),
                "event": log.event,
                "message": log.message,
                "json": log.json,
                "created_at": log.created_at.isoformat() if log.created_at else None
            }
            for log in logs
        ]

        trip_data = {
            "id": str(trip_obj.id),
            "trucking_company_id": str(trip_obj.trucking_company_id),
            "ref": trip_obj.ref,
            "layout_ref": trip_obj.layout_ref,
            "driver_id": str(trip_obj.driver_id) if trip_obj.driver_id else None,
            "vehicle_plate": trip_obj.vehicle_plate,
            "status": trip_obj.status,
            "summary": trip_obj.summary,
            "schedule_start_time": trip_obj.schedule_start_time.isoformat() if trip_obj.schedule_start_time else None,
            "schedule_end_time": trip_obj.schedule_end_time.isoformat() if trip_obj.schedule_end_time else None,
            "schedule_start_tolerance": trip_obj.schedule_start_tolerance,
            "schedule_end_tolerance": trip_obj.schedule_end_tolerance,
            "custom_data": trip_obj.custom_data,
            
            # Origin fields
            "origin_street": trip_obj.origin_street,
            "origin_number": trip_obj.origin_number,
            "origin_city": trip_obj.origin_city,
            "origin_state": trip_obj.origin_state,
            "origin_country": trip_obj.origin_country,
            "origin_zip": trip_obj.origin_zip,
            "origin_lat": trip_obj.origin_lat,
            "origin_lng": trip_obj.origin_lng,
            
            # Destiny fields
            "destiny_street": trip_obj.destiny_street,
            "destiny_number": trip_obj.destiny_number,
            "destiny_city": trip_obj.destiny_city,
            "destiny_state": trip_obj.destiny_state,
            "destiny_country": trip_obj.destiny_country,
            "destiny_zip": trip_obj.destiny_zip,
            "destiny_lat": trip_obj.destiny_lat,
            "destiny_lng": trip_obj.destiny_lng,
            
            "from_location": trip_obj.from_location,
            "to_location": trip_obj.to_location,
            "created_at": trip_obj.created_at.isoformat() if trip_obj.created_at else None,
            "updated_at": trip_obj.updated_at.isoformat() if trip_obj.updated_at else None
        }

        # Query driver metadata
        driver = driver_map.get(trip_obj.driver_id) if trip_obj.driver_id else None
        driver_data = {
            "tax_id": driver.tax_id,
            "driver_license_number": driver.driver_license_number,
            "driver_license_category": driver.driver_license_category
        } if driver else None

        result.append({
            "ref": ref,
            "found": True,
            "data": {
                "trip": trip_data,
                "driver": driver_data,
                "logs": serialized_logs
            }
        })

    return {"success": True, "data": result}
