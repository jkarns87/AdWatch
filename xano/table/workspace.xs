table "workspace" {
  auth = false
  schema {
    int id
    timestamp created_at?=now
    text name filters=trim
    int owner_id {
      table = "user"
    }
    enum plan?="free" {
      values = ["free", "team", "agency"]
    }
  }
  index = [
    {type: "primary", field: [{name: "id"}]}
    {type: "btree", field: [{name: "owner_id"}]}
  ]
  guid = "7TLB4Z9rLphbGvtfv3jpoVyPRc0"
}
