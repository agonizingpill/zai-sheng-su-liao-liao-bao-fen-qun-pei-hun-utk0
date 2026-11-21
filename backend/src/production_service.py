from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from decimal import Decimal,ROUND_HALF_UP
from math import sqrt
from fastapi import HTTPException
from sqlalchemy import select,func
from .database import Session
from .models import Blend
from .quality_models import PelletCheck
from .production_models import Dryer,DryingRun,PelletPack,BlendShipment,ShipmentPack,LossRange,ShipmentWeighing,ShipmentSettlement
from .blending import obj,get,audit,view
from .constants import MIN_LOSS_SAMPLES,LOSS_BAND_SIGMA,LOSS_NOTE_MIN,LOSS_MIN_HALF_WIDTH_PCT,LOSS_BAND_EDGES

def stamp(v):return (v.replace(tzinfo=ZoneInfo('Asia/Shanghai'))if v.tzinfo is None else v).astimezone(timezone.utc)
def now():return datetime.now(timezone.utc).isoformat()
def q4(v):return Decimal(str(v)).quantize(Decimal('.0001'),rounding=ROUND_HALF_UP)
def dry_view(s,x):return {**obj(x),'blend_code':s.get(Blend,x.blend_id).code,'dryer_code':s.get(Dryer,x.dryer_id).code}
def pack_view(s,x):
    p=s.get(PelletCheck,x.check_id)
    return {**obj(x),'blend_code':s.get(Blend,p.blend_id).code,'certificate_code':p.certificate_code}
def weight_band(dispatch_kg):
    kg=Decimal(str(dispatch_kg))
    for i,edge in enumerate(LOSS_BAND_EDGES):
        if kg<Decimal(str(edge)):return i
    return len(LOSS_BAND_EDGES)
def band_bounds(band):
    lo=Decimal(str(LOSS_BAND_EDGES[band-1])) if band>0 else Decimal(0)
    hi=Decimal(str(LOSS_BAND_EDGES[band])) if band<len(LOSS_BAND_EDGES) else None
    return lo,hi
def band_label(band):
    lo,hi=band_bounds(band)
    return f'{int(lo)}-{int(hi)}kg' if hi is not None else f'{int(lo)}kg以上'
def weighing_view(x):
    d=obj(x);d['kind_label']={'receipt':'签收原秤','reweigh':'复秤'}.get(x.kind,x.kind);return d
def settlement_view(x):
    if not x:return None
    d=obj(x);d['state_label']={'closed':'已结案','suspended':'挂起对账'}.get(x.state,x.state);d['sample_approved']=bool(x.approved_by);return d
def range_view(x):
    d=obj(x);d['sigma_used']=float(q4(Decimal(str(x.upper_pct))-Decimal(str(x.mean_loss_pct))));return d
def active_range(s,customer,band):
    return s.scalar(select(LossRange).where(LossRange.customer==customer,LossRange.weight_band==band).order_by(LossRange.version.desc()).limit(1))
def ship_view(s,x):
    packs=[{**obj(link),'pack_code':s.get(PelletPack,link.pack_id).code}for link in s.scalars(select(ShipmentPack).where(ShipmentPack.shipment_id==x.id).order_by(ShipmentPack.id))]
    weighings=[weighing_view(w)for w in s.scalars(select(ShipmentWeighing).where(ShipmentWeighing.shipment_id==x.id).order_by(ShipmentWeighing.id))]
    settlement=settlement_view(s.scalar(select(ShipmentSettlement).where(ShipmentSettlement.shipment_id==x.id)))
    return {**obj(x),'packs':packs,'total_kg':float(sum((Decimal(str(p['pack_snapshot']['kg']))for p in packs),Decimal(0))),'weighings':weighings,'settlement':settlement,'booked_kg':settlement['booked_kg'] if settlement else None,'range_version':settlement['range_version'] if settlement else None}
def room(s,dryer_id,start,end,exclude=None):
    for x in s.scalars(select(DryingRun).where(DryingRun.dryer_id==dryer_id).with_for_update().execution_options(populate_existing=True)):
        if x.id!=exclude and datetime.fromisoformat(x.starts_at)<end and datetime.fromisoformat(x.ends_at)>start:raise HTTPException(409,'烘干设备在此时段已有作业，不能重叠占用')
def create_dry(s,p,u):
    dryer=get(s,Dryer,p.dryer_id,True)
    if dryer.state!='active':raise HTTPException(409,'烘干设备已停用')
    blend=get(s,Blend,p.blend_id,True)
    if blend.status!='released':raise HTTPException(409,'只有已投料配方可安排烘干')
    if s.scalar(select(DryingRun.id).where(DryingRun.blend_id==blend.id)):raise HTTPException(409,'配方已有烘干作业，需在原单延烘复测')
    start,end=stamp(p.starts_at),stamp(p.ends_at)
    if end<=start:raise HTTPException(409,'烘干结束须晚于开始')
    room(s,dryer.id,start,end);snap=view(s,blend);weight=sum(Decimal(str(x['kg']))for x in snap['portions'])
    moisture=sum(Decimal(str(x['kg']))*Decimal(str(x['moisture_snapshot']))for x in snap['portions'])/weight
    x=DryingRun(blend_id=blend.id,dryer_id=dryer.id,input_moisture=moisture.quantize(Decimal('.0001')),starts_at=start.isoformat(),ends_at=end.isoformat(),state='drying',measurements=[],input_snapshot=snap);s.add(x);s.flush();audit(s,u,'drying_started',blend.code);return dry_view(s,x)
def measure_dry(s,id,p,u):
    candidate=get(s,DryingRun,id);get(s,Dryer,candidate.dryer_id,True);x=get(s,DryingRun,id,True)
    if x.state not in ('drying','redry'):raise HTTPException(409,'仅烘干中或待延烘可复测，合格或已验收结果冻结')
    end=stamp(p.ends_at)
    if end<datetime.fromisoformat(x.ends_at):raise HTTPException(409,'延烘复测结束时间不得早于已占用结束时间')
    room(s,x.dryer_id,datetime.fromisoformat(x.starts_at),end,x.id)
    x.ends_at=end.isoformat();x.after_moisture=p.after_moisture;x.state='passed'if p.after_moisture<=Decimal('.05')else'redry'
    x.measurements=[*x.measurements,{'after_moisture':float(p.after_moisture),'ends_at':x.ends_at,'note':p.note,'actor':u['email'],'at':now()}];audit(s,u,'drying_measured',str(x.id)+' / '+x.state);return dry_view(s,x)
def accept_dry(s,id,u):
    x=get(s,DryingRun,id,True)
    if x.state!='passed':raise HTTPException(409,'烘后含水须≤0.05%且未验收，才能主管确认')
    x.state='accepted';x.accepted_by=u['email'];audit(s,u,'drying_accepted',str(x.id));return dry_view(s,x)
def accepted_drying(s,blend_id):
    x=s.scalar(select(DryingRun).where(DryingRun.blend_id==blend_id,DryingRun.state=='accepted'))
    if not x:raise HTTPException(409,'成品新签证须有同配方主管验收合格的烘干作业')
    return dry_view(s,x)
def available_pack_weight(s,p,kg,exclude=None):
    used=sum((x.kg for x in s.scalars(select(PelletPack).where(PelletPack.check_id==p.id,PelletPack.state!='cancelled').with_for_update().execution_options(populate_existing=True))if x.id!=exclude),Decimal(0))
    if used+kg>p.actual_kg:raise HTTPException(409,'累计有效包装重量超过合格粒料产出，不分配超额箱码')
def create_pack(s,p,u):
    check=get(s,PelletCheck,p.check_id,True)
    if check.state!='certified':raise HTTPException(409,'仅主管已发合格证的成品可以包装')
    available_pack_weight(s,check,p.kg);x=PelletPack(**p.model_dump(),state='open',certificate_snapshot=check.certificate_snapshot);s.add(x);s.flush();audit(s,u,'pack_created',x.code);return pack_view(s,x)
def change_pack(s,id,p,u):
    candidate=get(s,PelletPack,id);check=get(s,PelletCheck,candidate.check_id,True);x=get(s,PelletPack,id,True)
    if x.state!='open':raise HTTPException(409,'只有未封包装可改重量，封包与出库后冻结')
    available_pack_weight(s,check,p.kg,x.id);x.kg=p.kg;audit(s,u,'pack_reweighed',x.code);return pack_view(s,x)
def pack_action(s,id,u,target):
    candidate=get(s,PelletPack,id);get(s,PelletCheck,candidate.check_id,True);x=get(s,PelletPack,id,True)
    if x.state!='open':raise HTTPException(409,'仅未封包装可封包或取消，不可重复')
    x.state=target;audit(s,u,'pack_'+target,x.code);return pack_view(s,x)
def load_pack(s,id,p,u):
    sh=get(s,BlendShipment,id,True)
    if sh.state!='loading':raise HTTPException(409,'发车后清单冻结，不能继续装车')
    pack=get(s,PelletPack,p.pack_id,True)
    if pack.state!='sealed':raise HTTPException(409,'只有已封箱且未装车箱码可装入清单')
    if s.scalar(select(ShipmentPack.id).where(ShipmentPack.pack_id==pack.id)):raise HTTPException(409,'箱码已装车，不得重复出库')
    check=get(s,PelletCheck,pack.check_id)
    for link in s.scalars(select(ShipmentPack).where(ShipmentPack.shipment_id==sh.id)):
        previous=get(s,PelletCheck,get(s,PelletPack,link.pack_id).check_id)
        if previous.blend_id!=check.blend_id:raise HTTPException(409,'同一车次只允许同配方成品，不可跨配方混装')
    s.add(ShipmentPack(shipment_id=sh.id,pack_id=pack.id,pack_snapshot=pack_view(s,pack)));pack.state='loaded';s.flush();audit(s,u,'shipment_loaded',sh.code+' / '+pack.code);return ship_view(s,sh)
def dispatch(s,id,u):
    sh=get(s,BlendShipment,id,True)
    if sh.state!='loading':raise HTTPException(409,'仅装车中清单可发车，不可重复出库')
    snap=ship_view(s,sh)
    if not snap['packs']:raise HTTPException(409,'清单没有已封箱成品，不能发车')
    sh.manifest={'code':sh.code,'customer':sh.customer,'packs':snap['packs'],'total_kg':snap['total_kg'],'at':now(),'dispatched_by':u['email']};sh.dispatched_by=u['email'];sh.state='dispatched';audit(s,u,'shipment_dispatched',sh.code);return ship_view(s,sh)
def _loss(dispatch_kg,weight_kg):
    loss_kg=dispatch_kg-weight_kg;loss_pct=q4(loss_kg/dispatch_kg*Decimal(100));return loss_kg,loss_pct
def judge_loss(s,customer,dispatch_kg,loss_pct):
    rng=active_range(s,customer,weight_band(dispatch_kg))
    if not rng:return 'insufficient',None
    if Decimal(str(rng.lower_pct))<=loss_pct<=Decimal(str(rng.upper_pct)):return 'within',rng.version
    return 'outside',rng.version
def latest_weighing(s,shipment_id):
    return s.scalar(select(ShipmentWeighing).where(ShipmentWeighing.shipment_id==shipment_id).order_by(ShipmentWeighing.id.desc()).limit(1))
def _ensure_legacy(s,sh,u):
    """V3 旧数据只有 receipt_snapshot、state=received；首次进入新流程时补原秤与挂起结案。"""
    if sh.state!='received' or sh.receipt_snapshot is None or not sh.manifest:return
    if latest_weighing(s,sh.id):sh.state='suspended';return
    snap=sh.receipt_snapshot;dispatch_kg=Decimal(str(sh.manifest['total_kg']));weight=Decimal(str(snap['received_kg']))
    note=str(snap.get('difference_note')or'')
    w=_weighing(s,sh,'receipt',weight,note,snap.get('received_by'),u)
    s.add(ShipmentSettlement(shipment_id=sh.id,weighing_id=w.id,state='suspended',judgment=w.judgment,range_version=w.range_version,dispatch_kg=dispatch_kg,weight_band=weight_band(dispatch_kg),booked_kg=None,loss_kg=w.loss_kg,loss_pct=w.loss_pct,note=note,settled_by=u['email'],at=now()))
    sh.state='suspended';s.flush();audit(s,u,'shipment_legacy_migrated',sh.code)
def _weighing(s,sh,kind,weight,note,received_by,u):
    dispatch_kg=Decimal(str(sh.manifest['total_kg']));loss_kg,loss_pct=_loss(dispatch_kg,weight)
    judgment,version=judge_loss(s,sh.customer,dispatch_kg,loss_pct)
    w=ShipmentWeighing(shipment_id=sh.id,kind=kind,weight_kg=weight,dispatch_kg=dispatch_kg,loss_kg=loss_kg,loss_pct=loss_pct,judgment=judgment,range_version=version,note=note,received_by=received_by,recorded_by=u['email'],at=now())
    s.add(w);s.flush();return w
def receive(s,id,p,u):
    sh=get(s,BlendShipment,id,True)
    if sh.state!='dispatched':raise HTTPException(409,'仅已发车清单可签收原秤，不能重复签收')
    if s.scalar(select(ShipmentWeighing.id).where(ShipmentWeighing.shipment_id==sh.id,ShipmentWeighing.kind=='receipt')):raise HTTPException(409,'该车次已留存签收原秤，复秤请走复秤记录')
    if not sh.manifest:raise HTTPException(409,'发车清单未冻结，不能签收')
    note=p.difference_note.strip();dispatch_kg=Decimal(str(sh.manifest['total_kg']))
    weight=Decimal(str(p.received_kg));loss_kg,loss_pct=_loss(dispatch_kg,weight)
    if (loss_kg>0 or abs(loss_pct)>Decimal('.5'))and len(note)<LOSS_NOTE_MIN:raise HTTPException(409,'签收短重须填写至少8字说明后才能结案')
    w=_weighing(s,sh,'receipt',weight,note,p.received_by,u)
    sh.receipt_snapshot={'received_kg':float(weight),'received_by':p.received_by,'difference_note':note,'manifest_kg':float(dispatch_kg),'variance_pct':float(-loss_pct),'loss_pct':float(loss_pct),'judgment':w.judgment,'range_version':w.range_version,'at':now(),'recorded_by':u['email']}
    closed=w.judgment=='within'
    st=ShipmentSettlement(shipment_id=sh.id,weighing_id=w.id,state='closed'if closed else'suspended',judgment=w.judgment,range_version=w.range_version,dispatch_kg=dispatch_kg,weight_band=weight_band(dispatch_kg),booked_kg=weight if closed else None,loss_kg=loss_kg,loss_pct=loss_pct,note=note,settled_by=u['email'],at=now());s.add(st)
    sh.state='closed'if closed else'suspended';audit(s,u,'shipment_received',sh.code+' / '+w.judgment);audit(s,u,'shipment_closed'if closed else'shipment_suspended',sh.code+' / '+str(loss_pct)+'%');return ship_view(s,sh)
def reweigh(s,id,p,u):
    sh=get(s,BlendShipment,id,True);_ensure_legacy(s,sh,u)
    if sh.state=='closed':raise HTTPException(409,'车次已结案，重量冻结，不能再复秤')
    if not s.scalar(select(ShipmentWeighing.id).where(ShipmentWeighing.shipment_id==sh.id,ShipmentWeighing.kind=='receipt')):raise HTTPException(409,'请先完成签收原秤，再登记复秤')
    if sh.state!='suspended':raise HTTPException(409,'仅挂起对账的车次可复秤')
    note=p.note.strip()
    if len(note)<LOSS_NOTE_MIN:raise HTTPException(409,'复秤须填写至少8字复秤说明')
    w=_weighing(s,sh,'reweigh',Decimal(str(p.weight_kg)),note,p.received_by,u)
    audit(s,u,'shipment_reweighed',sh.code+' / '+w.judgment+' / v'+str(w.range_version));return ship_view(s,sh)
def settle(s,id,p,u):
    sh=get(s,BlendShipment,id,True);_ensure_legacy(s,sh,u)
    st=s.scalar(select(ShipmentSettlement).where(ShipmentSettlement.shipment_id==sh.id).with_for_update().execution_options(populate_existing=True))
    if not st:raise HTTPException(409,'尚未签收原秤，不能结案')
    if st.state=='closed':return ship_view(s,sh)
    w=latest_weighing(s,sh.id)
    if p.weighing_id!=w.id:raise HTTPException(409,'复秤已先办，不能按旧重量结案')
    if w.judgment!='within':raise HTTPException(409,'最新称重仍超正常损耗范围或样本不足，继续挂起对账')
    st.weighing_id=w.id;st.state='closed';st.judgment=w.judgment;st.range_version=w.range_version;st.booked_kg=w.weight_kg;st.loss_kg=w.loss_kg;st.loss_pct=w.loss_pct;st.settled_by=u['email'];st.at=now()
    if p.note.strip():st.note=p.note.strip()
    sh.state='closed';audit(s,u,'shipment_settled',sh.code+' / '+str(w.loss_pct)+'% / '+str(w.weight_kg)+'kg');return ship_view(s,sh)
def approve_sample(s,id,p,u):
    sh=get(s,BlendShipment,id,True);_ensure_legacy(s,sh,u)
    st=s.scalar(select(ShipmentSettlement).where(ShipmentSettlement.shipment_id==sh.id).with_for_update().execution_options(populate_existing=True))
    if not st:raise HTTPException(409,'尚未签收原秤，不能核准为正常样本')
    if st.approved_by:raise HTTPException(409,'该车次已核准为正常样本，不可重复核准')
    note=p.note.strip()
    if len(note)<LOSS_NOTE_MIN:raise HTTPException(409,'核准正常样本须填写至少8字依据')
    if Decimal(str(st.loss_pct))<0:raise HTTPException(409,'客户多收（负损耗）不是正常短重，不能核准为损耗样本')
    if st.state=='suspended':
        w=latest_weighing(s,sh.id)
        # 仅样本不足（尚无范围）可由主管人工核准为正常车次入账；超界须先复秤回到范围内。
        if w.judgment!='insufficient':raise HTTPException(409,'超正常损耗范围的车次须先复秤回到范围内并结案，才能核准为正常样本')
        st.weighing_id=w.id;st.state='closed';st.judgment=w.judgment;st.range_version=w.range_version;st.booked_kg=w.weight_kg;st.loss_kg=w.loss_kg;st.loss_pct=w.loss_pct;st.settled_by=u['email'];st.at=now();sh.state='closed';audit(s,u,'shipment_reconciled',sh.code+' / '+str(w.loss_pct)+'% / '+str(w.weight_kg)+'kg')
    st.approved_by=u['email'];st.approved_at=now();st.approval_note=note;audit(s,u,'shipment_sample_approved',sh.code+' / '+note);return ship_view(s,sh)
def fit_ranges(s,p,u):
    rows=s.execute(select(ShipmentSettlement,BlendShipment).join(BlendShipment,BlendShipment.id==ShipmentSettlement.shipment_id).where(ShipmentSettlement.state=='closed',ShipmentSettlement.approved_by.isnot(None))).all()
    groups={}
    for st,sh in rows:groups.setdefault((sh.customer,st.weight_band),[]).append(st)
    if p.customer and p.weight_band is not None:targets=[(p.customer,p.weight_band)]
    elif p.customer:targets=sorted(k for k in groups if k[0]==p.customer)
    elif p.weight_band is not None:targets=sorted(k for k in groups if k[1]==p.weight_band)
    else:targets=sorted(groups)
    created=[]
    for customer,band in targets:
        samples=groups.get((customer,band),[])
        if len(samples)<MIN_LOSS_SAMPLES:
            if p.customer or p.weight_band is not None:raise HTTPException(409,f'{customer} {band_label(band)}核准正常车次仅{len(samples)}车，少于{MIN_LOSS_SAMPLES}车，暂不拟合')
            continue
        values=[Decimal(str(x.loss_pct))for x in samples];n=len(values);mean=sum(values,Decimal(0))/n
        sigma=Decimal(str(sqrt(float(sum(((v-mean)**2 for v in values),Decimal(0))/(n-1)))))
        half=max(Decimal(LOSS_BAND_SIGMA)*sigma,Decimal(str(LOSS_MIN_HALF_WIDTH_PCT)))
        version=(s.scalar(select(func.max(LossRange.version)).where(LossRange.customer==customer,LossRange.weight_band==band))or 0)+1
        lo,hi=band_bounds(band)
        # 短重结案只覆盖短重：下界钳在 0，客户多收（负损耗）一律超界挂起对账。
        lower=max(q4(mean-half),Decimal(0));upper=max(q4(mean+half),lower+Decimal(str(LOSS_MIN_HALF_WIDTH_PCT)))
        x=LossRange(customer=customer,weight_band=band,band_min_kg=lo,band_max_kg=hi,version=version,sample_count=n,mean_loss_pct=q4(mean),std_loss_pct=q4(sigma),lower_pct=lower,upper_pct=upper,sample_ids=[st.id for st in samples],fitted_by=u['email'],fitted_at=now());s.add(x);s.flush();created.append(range_view(x));audit(s,u,'loss_range_fitted',f'{customer} / {band_label(band)} / v{version} / {n}车')
    if p.customer and not created:raise HTTPException(409,'该客户暂无达到样本量的正常车次，未生成范围')
    if p.weight_band is not None and not created:raise HTTPException(409,f'{band_label(p.weight_band)}暂无达到样本量的正常车次，未生成范围')
    return created
