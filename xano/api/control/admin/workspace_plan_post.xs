query "admin/workspace/{workspace_id}/plan" verb=POST {
  api_group = "control"
  description = "Set any workspace's plan. Platform staff only — this is the one action a caller can take against a workspace they are not a member of, so it is gated on user.is_platform_admin rather than on workspace_member.role, and every change is recorded in plan_change."
  auth = "user"
  input {
    int workspace_id
    enum plan {
      values = ["free", "team", "agency"]
    }
    text reason?=""
  }
  stack {
    // is_platform_admin is absent from tokens issued before the claim existed, so this
    // reads null and denies. Failing closed on an old token is the correct default.
    precondition ($auth.extras.is_platform_admin == true) {
      error_type = "accessdenied"
      error = "platform administration requires a platform admin"
    }

    db.get "workspace" {
      field_name = "id"
      field_value = $input.workspace_id
    } as $before

    precondition ($before != null) {
      error_type = "notfound"
      error = "workspace not found"
    }

    // Record the change before making it, and record it even when nothing moves — a
    // no-op attempt against someone else's workspace is still worth being able to see.
    db.add "plan_change" {
      data = {
        workspace_id: $before.id,
        actor_user_id: $auth.id,
        from_plan: $before.plan,
        to_plan: $input.plan,
        reason: $input.reason
      }
    } as $audit

    db.patch "workspace" {
      field_name = "id"
      field_value = $input.workspace_id
      data = { plan: $input.plan }
    } as $workspace
  }
  response = {
    id: $workspace.id,
    name: $workspace.name,
    plan: $workspace.plan,
    previous_plan: $before.plan,
    changed_by: $auth.id,
    audit_id: $audit.id
  }
  guid = "yDxw3EzKc5c5jUll9juUbCJUV-w"
}
