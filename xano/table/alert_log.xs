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
    enum status?="sent" {
      values = ["sent", "failed", "skipped"]
    }
    text detail?
  }
  index = [
    {type: "primary", field: [{name: "id"}]}
    {type: "btree", field: [{name: "workspace_id"}, {name: "created_at", op: "desc"}]}
  ]
  guid = "YXeI-Ggi-NtMaJjoCxEUXi4-JfU"
}
