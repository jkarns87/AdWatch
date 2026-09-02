table "user" {
  auth = true
  schema {
    int id
    timestamp created_at?=now
    text name filters=trim
    email email filters=trim|lower {
      sensitive = true
    }
    password password {
      sensitive = true
    }
    int default_workspace_id? {
      table = "workspace"
      description = "Workspace this user lands in on login"
    }
  }
  index = [
    {type: "primary", field: [{name: "id"}]}
    {type: "btree|unique", field: [{name: "email"}]}
  ]
}
