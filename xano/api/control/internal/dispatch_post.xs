query "internal/dispatch" verb=POST {
  api_group = "control"
  description = "Called by the data plane after /analyze. Fans one insight out to every enabled alert destination in the workspace (in-app inbox, Slack/Discord/Teams/generic webhooks, email). Protected by a shared secret header."
  input {
    int workspace_id
    int insight_id
    int watchlist_id?
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
                watchlist_id: $input.watchlist_id,
                channel: $pref.channel,
                severity: $input.severity,
                title: $input.title,
                summary: $input.summary,
                why_it_matters: $input.why_it_matters,
                dashboard_url: $input.dashboard_url,
                status: "skipped",
                detail: "below min_severity"
              }
            }
          }
          elseif ($pref.channel == "in_app") {
            db.add "alert_log" {
              data = {
                workspace_id: $input.workspace_id,
                alert_pref_id: $pref.id,
                insight_id: $input.insight_id,
                watchlist_id: $input.watchlist_id,
                channel: "in_app",
                severity: $input.severity,
                title: $input.title,
                summary: $input.summary,
                why_it_matters: $input.why_it_matters,
                dashboard_url: $input.dashboard_url,
                read: false,
                status: "sent",
                detail: "in_app"
              }
            }
            var.update $sent { value = $sent + 1 }
          }
          elseif ($pref.channel == "webhook") {
            var $payload { value = { text: $text, content: $text } }
            conditional {
              if ($pref.provider == "slack") {
                var $sev_icon { value = ":large_orange_circle:" }
                conditional {
                  if ($input.severity == "high") {
                    var.update $sev_icon { value = ":red_circle:" }
                  }
                  elseif ($input.severity == "low") {
                    var.update $sev_icon { value = ":large_green_circle:" }
                  }
                }
                var $why_block { value = "_Why it matters:_ " ~ $input.why_it_matters }
                conditional {
                  if ($input.why_it_matters == null || $input.why_it_matters == "") {
                    var.update $why_block { value = " " }
                  }
                }
                var $link { value = $input.dashboard_url }
                conditional {
                  if ($link == null || $link == "") {
                    var.update $link { value = "https://adwatch.example" }
                  }
                }
                var.update $payload {
                  value = {
                    text: "AdWatch · " ~ $input.title ~ " — " ~ ($input.severity|to_upper) ~ ": " ~ $input.summary,
                    blocks: [
                      { type: "header", text: { type: "plain_text", text: "AdWatch · " ~ $input.title, emoji: true } },
                      { type: "context", elements: [ { type: "mrkdwn", text: $sev_icon ~ " *" ~ ($input.severity|to_upper) ~ "* severity · insight #" ~ ($input.insight_id|to_text) } ] },
                      { type: "section", text: { type: "mrkdwn", text: $input.summary } },
                      { type: "section", text: { type: "mrkdwn", text: $why_block } },
                      { type: "actions", elements: [ { type: "button", text: { type: "plain_text", text: "Open in AdWatch", emoji: true }, url: $link, style: "primary" } ] }
                    ]
                  }
                }
              }
              elseif ($pref.provider == "teams") {
                var.update $payload {
                  value = {
                    type: "message",
                    attachments: [
                      {
                        contentType: "application/vnd.microsoft.card.adaptive",
                        content: {
                          type: "AdaptiveCard",
                          version: "1.4",
                          body: [
                            { type: "TextBlock", size: "Medium", weight: "Bolder", text: "AdWatch · " ~ $input.title ~ " — " ~ ($input.severity|to_upper) },
                            { type: "TextBlock", wrap: true, text: $input.summary },
                            { type: "TextBlock", wrap: true, isSubtle: true, text: $input.why_it_matters }
                          ],
                          actions: [
                            { type: "Action.OpenUrl", title: "Open in AdWatch", url: $input.dashboard_url }
                          ]
                        }
                      }
                    ]
                  }
                }
              }
            }

            api.request {
              url = $pref.target
              method = "POST"
              params = $payload
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
                    watchlist_id: $input.watchlist_id,
                    channel: "webhook",
                    severity: $input.severity,
                    title: $input.title,
                    summary: $input.summary,
                    status: "sent",
                    detail: ($pref.provider|to_text) ~ " webhook " ~ ($hook.response.status|to_text)
                  }
                }
              }
              else {
                db.add "alert_log" {
                  data = {
                    workspace_id: $input.workspace_id,
                    alert_pref_id: $pref.id,
                    insight_id: $input.insight_id,
                    watchlist_id: $input.watchlist_id,
                    channel: "webhook",
                    severity: $input.severity,
                    title: $input.title,
                    summary: $input.summary,
                    status: "failed",
                    detail: ($pref.provider|to_text) ~ " webhook " ~ ($hook.response.status|to_text)
                  }
                }
              }
            }
          }
          else {
            function.run "send_email" {
              input = {
                to: $pref.target,
                subject: "AdWatch alert: " ~ $input.title,
                message: $text
              }
            }
            var.update $sent { value = $sent + 1 }
            db.add "alert_log" {
              data = {
                workspace_id: $input.workspace_id,
                alert_pref_id: $pref.id,
                insight_id: $input.insight_id,
                watchlist_id: $input.watchlist_id,
                channel: "email",
                severity: $input.severity,
                title: $input.title,
                summary: $input.summary,
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
