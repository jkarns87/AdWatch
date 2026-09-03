function "issue_token" {
  description = "Issue a 7-day auth token carrying the user's workspace_id claim"
  input {
    int user_id
    int workspace_id
    text role
    bool is_platform_admin?=false
  }
  stack {
    security.create_auth_token {
      table = "user"
      id = $input.user_id
      extras = {
        workspace_id: $input.workspace_id,
        role: $input.role,
        is_platform_admin: $input.is_platform_admin
      }
      expiration = 604800
    } as $token
  }
  response = $token
  guid = "N6SvqR7yUHmOyIANtIUzhIFiMec"
}
