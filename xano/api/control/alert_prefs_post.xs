query "alert_prefs" verb=POST {
  api_group = "control"
  description = "Add an alert destination (webhook URL or email) for the caller's workspace"
  auth = "user"
  input {
    enum channel?="webhook" {
      values = ["webhook", "email"]
    }
    text target filters=trim
    enum min_severity?="medium" {
      values = ["low", "medium", "high"]
    }
  }
  stack {
    precondition (($input.target|strlen) > 3) {
      error_type = "inputerror"
      error = "target must be a webhook URL or an email address"
    }

    db.add "alert_pref" {
      data = {
        workspace_id: $auth.workspace_id,
        channel: $input.channel,
        target: $input.target,
        min_severity: $input.min_severity,
        enabled: true
      }
    } as $pref
  }
  response = $pref
}
