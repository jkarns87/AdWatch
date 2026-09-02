table "alert_log" {
  auth = false
  schema {
    int id
    timestamp created_at?=now
    int workspace_id {
      table = "workspace"
    }
    int alert_pref_id? {
      table = "alert_pref"
    }
    int insight_id? {
      description = "Data-plane insight id"
    }
    int watchlist_id? {
      description = "Data-plane watchlist id (for deep links)"
    }
    text channel?="webhook" {
      description = "in_app | webhook | email — copied from the alert_pref at dispatch time"
    }
    enum severity?="medium" {
      values = ["low", "medium", "high"]
    }
    text title?
    text summary?
    text why_it_matters?
    text dashboard_url?
    bool read?=false
    enum status?="sent" {
      values = ["sent", "failed", "skipped"]
    }
    text detail?
  }
  index = [
    {type: "primary", field: [{name: "id"}]}
    {type: "btree", field: [{name: "workspace_id"}, {name: "created_at", op: "desc"}]}
    {type: "btree", field: [{name: "workspace_id"}, {name: "read"}]}
  ]
  guid = "YXeI-Ggi-NtMaJjoCxEUXi4-JfU"
}
