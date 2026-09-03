query "workspace/plan" verb=POST {
  api_group = "control"
  description = "Change the caller's workspace plan (owner only). Plans gate watchlist/competitor/keyword counts and collection cadence — see docs/COST_MODEL.md."
  auth = "user"
  input {
    enum plan {
      values = ["free", "team", "agency"]
    }
  }
  stack {
    precondition ($auth.extras.role == "owner") {
      error_type = "accessdenied"
      error = "only the workspace owner can change the plan"
    }

    db.get "workspace" {
      field_name = "id"
      field_value = $auth.extras.workspace_id
    } as $before

    // Audited on the same table as the platform-admin path, so "who changed this
    // plan" has one answer regardless of which door the change came through.
    db.add "plan_change" {
      data = {
        workspace_id: $before.id,
        actor_user_id: $auth.id,
        from_plan: $before.plan,
        to_plan: $input.plan,
        reason: ""
      }
    } as $audit

    db.patch "workspace" {
      field_name = "id"
      field_value = $auth.extras.workspace_id
      data = { plan: $input.plan }
    } as $workspace
  }
  response = { id: $workspace.id, name: $workspace.name, plan: $workspace.plan }
  guid = "Qk3EybpTxYd-xh3QYKa9amNPAfk"
}
