table "password_reset" {
  auth = false
  schema {
    int id
    timestamp created_at?=now
    int user_id {
      table = "user"
    }
    text selector filters=trim {
      description = "Public half of the reset token. Stored in clear so the row can be looked up without comparing secrets."
    }
    password verifier {
      description = "Secret half, hashed by Xano. A database leak yields no usable reset link."
      sensitive = true
    }
    timestamp expires_at {
      description = "One hour after issue"
    }
    timestamp used_at? {
      description = "Set on redemption; a token is single-use"
    }
  }
  index = [
    {type: "primary", field: [{name: "id"}]}
    {type: "btree|unique", field: [{name: "selector"}]}
    {type: "btree", field: [{name: "user_id"}]}
  ]
  guid = "0xn9spRqAPqHVUSVM7N9aHJx91s"
}
