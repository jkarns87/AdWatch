function "issue_token" {
  description = "Issue a 7-day auth token carrying the user's workspace_id claim"
  input {
    int user_id
    int workspace_id
    text role
  }
  stack {
    security.create_auth_token {
      table = "user"
      id = $input.user_id
      extras = {
        workspace_id: $input.workspace_id,
        role: $input.role
      }
      expiration = 604800
    } as $token
  }
  response = $token
}
