table "workspace_member" {
  auth = false
  schema {
    int id
    timestamp created_at?=now
    int workspace_id {
      table = "workspace"
    }
    int user_id {
      table = "user"
    }
    enum role?="member" {
      values = ["owner", "member", "viewer"]
    }
  }
  index = [
    {type: "primary", field: [{name: "id"}]}
    {type: "btree|unique", field: [{name: "workspace_id"}, {name: "user_id"}]}
    {type: "btree", field: [{name: "user_id"}]}
  ]
}
