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
    bool is_platform_admin?=false {
      description = "Platform staff. Grants cross-workspace administration — changing another workspace's plan — and nothing else. Distinct from workspace_member.role, which only ever means something inside one workspace."
    }
  }
  index = [
    {type: "primary", field: [{name: "id"}]}
    {type: "btree|unique", field: [{name: "email"}]}
  ]
  guid = "CtAtCsbUfOhxYVQfVNHZ_Zwe7xk"
}
