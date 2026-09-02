table "alert_pref" {
  auth = false
  schema {
    int id
    timestamp created_at?=now
    int workspace_id {
      table = "workspace"
    }
    enum channel?="webhook" {
      values = ["webhook", "email"]
    }
    text target filters=trim {
      description = "Webhook URL or email address"
    }
    enum min_severity?="medium" {
      values = ["low", "medium", "high"]
    }
    bool enabled?=true
  }
  index = [
    {type: "primary", field: [{name: "id"}]}
    {type: "btree", field: [{name: "workspace_id"}]}
  ]
}
