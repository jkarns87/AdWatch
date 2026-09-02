query "alert_prefs" verb=GET {
  api_group = "control"
  description = "List alert preferences for the caller's workspace"
  auth = "user"
  input {}
  stack {
    db.query "alert_pref" {
      where = $db.alert_pref.workspace_id == $auth.extras.workspace_id
      sort = { created_at: "desc" }
      return = { type: "list" }
    } as $prefs
  }
  response = $prefs
  guid = "s2mGjdrL9Jz8oZ0DbFLoKVmkg-o"
}
