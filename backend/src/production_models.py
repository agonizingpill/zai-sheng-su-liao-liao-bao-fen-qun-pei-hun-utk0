from decimal import Decimal
from sqlalchemy import String,Numeric,ForeignKey,JSON,CheckConstraint,UniqueConstraint,Integer,BigInteger
from sqlalchemy.orm import Mapped,mapped_column
from .database import Base
class Dryer(Base):
    __tablename__='dryers'
    id:Mapped[int]=mapped_column(primary_key=True)
    code:Mapped[str]=mapped_column(String(40),unique=True)
    state:Mapped[str]=mapped_column(String(20),default='active')
class DryingRun(Base):
    __tablename__='drying_runs'
    id:Mapped[int]=mapped_column(primary_key=True)
    blend_id:Mapped[int]=mapped_column(ForeignKey('blends.id'),unique=True)
    dryer_id:Mapped[int]=mapped_column(ForeignKey('dryers.id'))
    input_moisture:Mapped[Decimal]=mapped_column(Numeric(9,4))
    after_moisture:Mapped[Decimal|None]=mapped_column(Numeric(9,4),nullable=True)
    starts_at:Mapped[str]=mapped_column(String(40))
    ends_at:Mapped[str]=mapped_column(String(40))
    state:Mapped[str]=mapped_column(String(20),default='drying')
    measurements:Mapped[list]=mapped_column(JSON)
    input_snapshot:Mapped[dict]=mapped_column(JSON)
    accepted_by:Mapped[str|None]=mapped_column(String(120),nullable=True)
class PelletPack(Base):
    __tablename__='pellet_packs'
    __table_args__=(CheckConstraint('kg > 0'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    check_id:Mapped[int]=mapped_column(ForeignKey('pellet_checks.id'))
    code:Mapped[str]=mapped_column(String(80),unique=True)
    kg:Mapped[Decimal]=mapped_column(Numeric(12,3))
    state:Mapped[str]=mapped_column(String(20),default='open')
    certificate_snapshot:Mapped[dict]=mapped_column(JSON)
class BlendShipment(Base):
    __tablename__='blend_shipments'
    id:Mapped[int]=mapped_column(primary_key=True)
    code:Mapped[str]=mapped_column(String(70),unique=True)
    customer:Mapped[str]=mapped_column(String(120))
    state:Mapped[str]=mapped_column(String(20),default='loading')
    manifest:Mapped[dict|None]=mapped_column(JSON,nullable=True)
    receipt_snapshot:Mapped[dict|None]=mapped_column(JSON,nullable=True)
    dispatched_by:Mapped[str|None]=mapped_column(String(120),nullable=True)
class ShipmentPack(Base):
    __tablename__='shipment_packs'
    id:Mapped[int]=mapped_column(primary_key=True)
    shipment_id:Mapped[int]=mapped_column(ForeignKey('blend_shipments.id'))
    pack_id:Mapped[int]=mapped_column(ForeignKey('pellet_packs.id'),unique=True)
    pack_snapshot:Mapped[dict]=mapped_column(JSON)
class LossRange(Base):
    """按客户与发车重量档拟合的正常损耗范围；版本只判新秤，不回改旧判定。"""
    __tablename__='loss_ranges'
    __table_args__=(UniqueConstraint('customer','weight_band','version'),CheckConstraint('sample_count >= 0'))
    id:Mapped[int]=mapped_column(primary_key=True)
    customer:Mapped[str]=mapped_column(String(120))
    weight_band:Mapped[int]=mapped_column(Integer)
    band_min_kg:Mapped[Decimal]=mapped_column(Numeric(12,3))
    band_max_kg:Mapped[Decimal|None]=mapped_column(Numeric(12,3),nullable=True)
    version:Mapped[int]=mapped_column(Integer)
    sample_count:Mapped[int]=mapped_column(Integer)
    mean_loss_pct:Mapped[Decimal]=mapped_column(Numeric(9,4))
    std_loss_pct:Mapped[Decimal]=mapped_column(Numeric(9,4))
    lower_pct:Mapped[Decimal]=mapped_column(Numeric(9,4))
    upper_pct:Mapped[Decimal]=mapped_column(Numeric(9,4))
    sample_ids:Mapped[list]=mapped_column(JSON)
    fitted_by:Mapped[str]=mapped_column(String(120))
    fitted_at:Mapped[str]=mapped_column(String(40))
class ShipmentWeighing(Base):
    """签收原秤与每次复秤各自留档，判定在称重当时冻结。"""
    __tablename__='shipment_weighings'
    __table_args__=(CheckConstraint('weight_kg > 0'),)
    id:Mapped[int]=mapped_column(primary_key=True)
    shipment_id:Mapped[int]=mapped_column(ForeignKey('blend_shipments.id'))
    kind:Mapped[str]=mapped_column(String(20))
    weight_kg:Mapped[Decimal]=mapped_column(Numeric(12,3))
    dispatch_kg:Mapped[Decimal]=mapped_column(Numeric(12,3))
    loss_kg:Mapped[Decimal]=mapped_column(Numeric(12,3))
    loss_pct:Mapped[Decimal]=mapped_column(Numeric(9,4))
    judgment:Mapped[str]=mapped_column(String(20))
    range_version:Mapped[int|None]=mapped_column(Integer,nullable=True)
    note:Mapped[str]=mapped_column(String(600),default='')
    received_by:Mapped[str|None]=mapped_column(String(120),nullable=True)
    recorded_by:Mapped[str]=mapped_column(String(120))
    at:Mapped[str]=mapped_column(String(40))
class ShipmentSettlement(Base):
    """一车一结案；重试只返回原入账，不重复记账。"""
    __tablename__='shipment_settlements'
    id:Mapped[int]=mapped_column(primary_key=True)
    shipment_id:Mapped[int]=mapped_column(ForeignKey('blend_shipments.id'),unique=True)
    weighing_id:Mapped[int]=mapped_column(ForeignKey('shipment_weighings.id'))
    state:Mapped[str]=mapped_column(String(20),default='suspended')
    judgment:Mapped[str]=mapped_column(String(20))
    range_version:Mapped[int|None]=mapped_column(Integer,nullable=True)
    dispatch_kg:Mapped[Decimal]=mapped_column(Numeric(12,3))
    weight_band:Mapped[int]=mapped_column(Integer)
    booked_kg:Mapped[Decimal|None]=mapped_column(Numeric(12,3),nullable=True)
    loss_kg:Mapped[Decimal]=mapped_column(Numeric(12,3))
    loss_pct:Mapped[Decimal]=mapped_column(Numeric(9,4))
    note:Mapped[str]=mapped_column(String(600),default='')
    approved_by:Mapped[str|None]=mapped_column(String(120),nullable=True)
    approved_at:Mapped[str|None]=mapped_column(String(40),nullable=True)
    approval_note:Mapped[str]=mapped_column(String(600),default='')
    settled_by:Mapped[str]=mapped_column(String(120))
    at:Mapped[str]=mapped_column(String(40))
