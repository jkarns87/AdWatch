table "plan_change" {
  description = "Who changed which workspace's plan, from what to what. Cross-workspace administration is the one action a user can take with no standing in the workspace it affects, so it is the one action that must not be deniable afterwards. Append-only: nothing in the API updates or deletes these rows."
  schema {
    int id
    timestamp created_at?=now
    int workspace_id {
      table = "workspace"
      description = "The workspace whose plan changed"
    }
    int actor_user_id {
      table = "user"
      description = "Who made the change. A platform admin for cross-workspace changes, the owner for their own."
    }
    text from_plan
    text to_plan
    text reason?="" {
      description = "Free text from the operator. Empty for self-service owner changes."
    }
  }
  index = [
    {type: "primary", field: [{name: "id"}]}
    {type: "btree", field: [{name: "workspace_id"}]}
    {type: "btree", field: [{name: "actor_user_id"}]}
  ]
  guid = "e5J8DEQQnt_i1M-LeKdGqbE5Fic"
}
