table "alert_pref" {
  auth = false
  schema {
    int id
    timestamp created_at?=now
    int workspace_id {
      table = "workspace"
    }
    enum channel?="webhook" {
      values = ["in_app", "webhook", "email"]
    }
    text provider? filters=trim {
      description = "in_app | slack | discord | teams | generic | email — drives payload shape and the UI icon"
    }
    text label? filters=trim {
      description = "Human name shown in Settings, e.g. 'Growth team channel'"
    }
    text target? filters=trim {
      description = "Webhook URL or email address; empty for in_app"
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
  guid = "p8CSKx3gi2OJH8S50pbxjKRrgAI"
}
