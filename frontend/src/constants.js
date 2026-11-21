export const ROLES={admin:'投料主管',blender:'配混员',viewer:'质检观察员'};
export const BLEND_STATES={draft:'待称料',ready:'审秤通过',released:'已投料'};
export const AUDIT_ACTIONS={bale_received:'来料登记',bale_retested:'料包复检',blend_created:'配方立单',weighed:'称料保存',checked:'审秤通过',blend_reopened:'退回秤台',released:'主管投料放行',shipment_received:'签收原秤留存',shipment_closed:'范围内直接结案',shipment_suspended:'超界/样本少挂起对账',shipment_reweighed:'复秤另存判定',shipment_settled:'按最新秤结案入账',shipment_sample_approved:'主管核准正常样本',loss_range_fitted:'拟合正常损耗范围'};

export const LOT_STATES={active:'来料可用',quarantine:'整批隔离'};
export const PELLET_STATES={quarantine:'PVC越限隔离',passed:'检验合格待签证',certified:'主管已发合格证'};

export const DRYING_STATES={drying:'烘干中',redry:'超含水待延烘',passed:'含水合格待验收',accepted:'主管已验收'};
export const PACK_STATES={open:'未封可调整',sealed:'已封箱',cancelled:'未封取消',loaded:'已装车冻结'};
export const SHIPMENT_STATES={loading:'装车中',dispatched:'已发车',received:'客户已签收',suspended:'挂起对账',closed:'已结案'};
export const WEIGHING_KINDS={receipt:'签收原秤',reweigh:'复秤'};
export const LOSS_JUDGMENTS={within:'在正常损耗范围',outside:'超正常损耗范围',insufficient:'样本不足待拟合'};
export const SETTLEMENT_STATES={closed:'已结案',suspended:'挂起对账'};
