ROLES=('admin','blender','viewer')
BLEND_STATES=('draft','ready','released')

LOT_STATES=('active','quarantine')
PELLET_STATES=('quarantine','passed','certified')

DRYING_STATES=('drying','redry','passed','accepted')
PACK_STATES=('open','sealed','cancelled','loaded')
SHIPMENT_STATES=('loading','dispatched','received','suspended','closed')

# 签收短重结案：签收原秤 + 复秤各留一条称重记录，结案只入账一次。
WEIGHING_KINDS=('receipt','reweigh')
LOSS_JUDGMENTS=('within','outside','insufficient')
SETTLEMENT_STATES=('closed','suspended')

# 正常损耗范围：只用主管核准的正常车次；样本不足时不拟合，签收挂起对账。
MIN_LOSS_SAMPLES=5
LOSS_BAND_SIGMA=3
# 发车重量档边界（kg）：0-100 / 100-500 / 500-1000 / 1000-5000 / 5000-10000 / 10000+
LOSS_BAND_EDGES=(100,500,1000,5000,10000)
# σ 过小时的范围下限，避免少量样本拟合出零宽区间。
LOSS_MIN_HALF_WIDTH_PCT='0.05'
LOSS_NOTE_MIN=8
