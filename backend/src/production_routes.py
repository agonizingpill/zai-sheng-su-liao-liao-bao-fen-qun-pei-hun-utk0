from fastapi import APIRouter,Depends
from sqlalchemy import select
from .database import Session
from .security import current,allow
from .blending import obj,audit
from .production_models import Dryer,DryingRun,PelletPack,BlendShipment,LossRange
from .production_schemas import DryerInput,DryingInput,DryingMeasure,PackInput,PackWeight,ShipmentInput,LoadPack,ShipmentReceipt,ShipmentReweigh,ShipmentSettle,SampleApproval,LossRangeFit
from . import production_service as svc
router=APIRouter()
@router.get('/dryers')
def dryers(u=Depends(current)):
    with Session()as s:return [obj(x)for x in s.scalars(select(Dryer).order_by(Dryer.id))]
@router.post('/dryers')
def dryer(p:DryerInput,u=Depends(current)):
    allow(u,'admin')
    with Session.begin()as s:
        x=Dryer(code=p.code,state='active');s.add(x);s.flush();audit(s,u,'dryer_registered',x.code);return obj(x)
@router.get('/drying-runs')
def drying(u=Depends(current)):
    with Session()as s:return [svc.dry_view(s,x)for x in s.scalars(select(DryingRun).order_by(DryingRun.id.desc()))]
@router.post('/drying-runs')
def dry(p:DryingInput,u=Depends(current)):
    allow(u,'admin','blender')
    with Session.begin()as s:return svc.create_dry(s,p,u)
@router.post('/drying-runs/{id}/measure')
def measure(id:int,p:DryingMeasure,u=Depends(current)):
    allow(u,'admin','blender')
    with Session.begin()as s:return svc.measure_dry(s,id,p,u)
@router.post('/drying-runs/{id}/accept')
def accept(id:int,u=Depends(current)):
    allow(u,'admin')
    with Session.begin()as s:return svc.accept_dry(s,id,u)
@router.get('/pellet-packs')
def packs(u=Depends(current)):
    with Session()as s:return [svc.pack_view(s,x)for x in s.scalars(select(PelletPack).order_by(PelletPack.id.desc()))]
@router.post('/pellet-packs')
def pack(p:PackInput,u=Depends(current)):
    allow(u,'admin','blender')
    with Session.begin()as s:return svc.create_pack(s,p,u)
@router.patch('/pellet-packs/{id}')
def reweigh(id:int,p:PackWeight,u=Depends(current)):
    allow(u,'admin','blender')
    with Session.begin()as s:return svc.change_pack(s,id,p,u)
@router.post('/pellet-packs/{id}/seal')
def seal(id:int,u=Depends(current)):
    allow(u,'admin','blender')
    with Session.begin()as s:return svc.pack_action(s,id,u,'sealed')
@router.post('/pellet-packs/{id}/cancel')
def cancel(id:int,u=Depends(current)):
    allow(u,'admin','blender')
    with Session.begin()as s:return svc.pack_action(s,id,u,'cancelled')
@router.get('/blend-shipments')
def shipments(u=Depends(current)):
    with Session()as s:return [svc.ship_view(s,x)for x in s.scalars(select(BlendShipment).order_by(BlendShipment.id.desc()))]
@router.post('/blend-shipments')
def shipment(p:ShipmentInput,u=Depends(current)):
    allow(u,'admin','blender')
    with Session.begin()as s:
        x=BlendShipment(**p.model_dump(),state='loading');s.add(x);s.flush();audit(s,u,'shipment_created',x.code);return svc.ship_view(s,x)
@router.post('/blend-shipments/{id}/packs')
def load(id:int,p:LoadPack,u=Depends(current)):
    allow(u,'admin','blender')
    with Session.begin()as s:return svc.load_pack(s,id,p,u)
@router.post('/blend-shipments/{id}/dispatch')
def dispatch(id:int,u=Depends(current)):
    allow(u,'admin')
    with Session.begin()as s:return svc.dispatch(s,id,u)
@router.post('/blend-shipments/{id}/receive')
def receive(id:int,p:ShipmentReceipt,u=Depends(current)):
    allow(u,'admin','blender')
    with Session.begin()as s:return svc.receive(s,id,p,u)
@router.post('/blend-shipments/{id}/reweigh')
def reweigh_shipment(id:int,p:ShipmentReweigh,u=Depends(current)):
    allow(u,'admin','blender')
    with Session.begin()as s:return svc.reweigh(s,id,p,u)
@router.post('/blend-shipments/{id}/settle')
def settle(id:int,p:ShipmentSettle,u=Depends(current)):
    allow(u,'admin','blender')
    with Session.begin()as s:return svc.settle(s,id,p,u)
@router.post('/blend-shipments/{id}/approve-sample')
def approve_sample(id:int,p:SampleApproval,u=Depends(current)):
    allow(u,'admin')
    with Session.begin()as s:return svc.approve_sample(s,id,p,u)
@router.get('/loss-ranges')
def loss_ranges(u=Depends(current)):
    with Session()as s:return [svc.range_view(x)for x in s.scalars(select(LossRange).order_by(LossRange.customer,LossRange.weight_band,LossRange.version.desc()))]
@router.post('/loss-ranges/fit')
def fit(p:LossRangeFit,u=Depends(current)):
    allow(u,'admin')
    with Session.begin()as s:return svc.fit_ranges(s,p,u)
