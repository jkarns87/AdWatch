query "alert_prefs" verb=POST {
  api_group = "control"
  description = "Add an alert destination for the caller's workspace: in-app inbox, a Slack/Discord/Teams/generic webhook URL, or an email address"
  auth = "user"
  input {
    enum channel?="webhook" {
      values = ["in_app", "webhook", "email"]
    }
    text provider? filters=trim|lower {
      description = "in_app | slack | discord | teams | generic | email"
    }
    text label? filters=trim
    text target? filters=trim
    enum min_severity?="medium" {
      values = ["low", "medium", "high"]
    }
  }
  stack {
    precondition ($input.channel == "in_app" || ($input.target|strlen) > 3) {
      error_type = "inputerror"
      error = "target must be a webhook URL or an email address"
    }

    var $provider { value = $input.provider }
    conditional {
      if (($provider == null || $provider == "") && $input.channel == "in_app") {
        var.update $provider { value = "in_app" }
      }
      elseif (($provider == null || $provider == "") && $input.channel == "email") {
        var.update $provider { value = "email" }
      }
      elseif ($provider == null || $provider == "") {
        var.update $provider { value = "generic" }
      }
    }

    db.add "alert_pref" {
      data = {
        workspace_id: $auth.extras.workspace_id,
        channel: $input.channel,
        provider: $provider,
        label: $input.label,
        target: $input.target,
        min_severity: $input.min_severity,
        enabled: true
      }
    } as $pref
  }
  response = $pref
  guid = "6FTeE9UAh5D-HpFILsgU3JyhdJg"
}
