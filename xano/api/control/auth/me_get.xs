query "auth/me" verb=GET {
  api_group = "control"
  description = "Who am I. Also used by the data plane to introspect bearer tokens (returns workspace_id)."
  auth = "user"
  input {}
  stack {
    db.get "user" {
      field_name = "id"
      field_value = $auth.id
    } as $user

    db.get "workspace" {
      field_name = "id"
      field_value = $auth.workspace_id
    } as $workspace
  }
  response = {
    id: $user.id,
    name: $user.name,
    email: $user.email,
    workspace_id: $auth.workspace_id,
    role: $auth.role,
    workspace: { id: $workspace.id, name: $workspace.name, plan: $workspace.plan }
  }
  guid = "FKw5aKvGQPd7Dmr5RWmgVD8ctJA"
}
