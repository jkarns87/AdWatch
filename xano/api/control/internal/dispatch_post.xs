query "internal/dispatch" verb=POST {
  api_group = "control"
  description = "Called by the data plane after /analyze. Fans one insight out to every enabled alert destination in the workspace. Protected by a shared secret header."
  input {
    int workspace_id
    int insight_id
    text severity filters=trim|lower
    text title filters=trim
    text summary
    text why_it_matters?
    json actions?
    text dashboard_url?
  }
  stack {
    var $secret { value = $env.$http_headers|get:"X-Dataplane-Secret" }
    precondition ($secret != null && $secret == $env.DATAPLANE_SHARED_SECRET) {
      error_type = "accessdenied"
      error = "bad shared secret"
    }

    var $rank { value = { low: 0, medium: 1, high: 2 } }
    var $sev_rank { value = $rank|get:$input.severity:0 }

    db.query "alert_pref" {
      where = $db.alert_pref.workspace_id == $input.workspace_id && $db.alert_pref.enabled == true
      return = { type: "list" }
    } as $prefs

    var $text {
      value = "*AdWatch · " ~ $input.title ~ "* — " ~ ($input.severity|to_upper) ~ "\n" ~ $input.summary
    }
    conditional {
      if ($input.why_it_matters != null && $input.why_it_matters != "") {
        var.update $text { value = $text ~ "\n_Why it matters:_ " ~ $input.why_it_matters }
      }
    }
    conditional {
      if ($input.dashboard_url != null && $input.dashboard_url != "") {
        var.update $text { value = $text ~ "\n" ~ $input.dashboard_url }
      }
    }

    var $sent { value = 0 }

    foreach ($prefs) {
      each as $pref {
        var $min_rank { value = $rank|get:$pref.min_severity:1 }

        conditional {
          if ($sev_rank < $min_rank) {
            db.add "alert_log" {
              data = {
                workspace_id: $input.workspace_id,
                alert_pref_id: $pref.id,
                insight_id: $input.insight_id,
                status: "skipped",
                detail: "below min_severity"
              }
            }
          }
          elseif ($pref.channel == "webhook") {
            api.request {
              url = $pref.target
              method = "POST"
              params = { text: $text, content: $text }
              headers = ["Content-Type: application/json"]
              timeout = 10
            } as $hook

            conditional {
              if ($hook.response.status >= 200 && $hook.response.status < 300) {
                var.update $sent { value = $sent + 1 }
                db.add "alert_log" {
                  data = {
                    workspace_id: $input.workspace_id,
                    alert_pref_id: $pref.id,
                    insight_id: $input.insight_id,
                    status: "sent",
                    detail: "webhook " ~ ($hook.response.status|to_text)
                  }
                }
              }
              else {
                db.add "alert_log" {
                  data = {
                    workspace_id: $input.workspace_id,
                    alert_pref_id: $pref.id,
                    insight_id: $input.insight_id,
                    status: "failed",
                    detail: "webhook " ~ ($hook.response.status|to_text)
                  }
                }
              }
            }
          }
          else {
            util.send_email {
              to = $pref.target
              subject = "AdWatch alert: " ~ $input.title
              message = $text
            }
            var.update $sent { value = $sent + 1 }
            db.add "alert_log" {
              data = {
                workspace_id: $input.workspace_id,
                alert_pref_id: $pref.id,
                insight_id: $input.insight_id,
                status: "sent",
                detail: "email"
              }
            }
          }
        }
      }
    }
  }
  response = { sent: $sent, destinations: $prefs|count }
  guid = "aki8nIbyAvNN1ZdIkBoVEi7ai3w"
}
