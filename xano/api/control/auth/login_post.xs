query "auth/login" verb=POST {
  api_group = "control"
  description = "Email + password login; returns an authToken with a workspace_id claim"
  input {
    email email filters=trim|lower
    text password {
      sensitive = true
    }
  }
  stack {
    db.query "user" {
      where = $db.user.email == $input.email
      return = { type: "single" }
    } as $user

    precondition ($user != null) {
      error_type = "accessdenied"
      error = "Invalid credentials"
    }

    security.check_password {
      text_password = $input.password
      hash_password = $user.password
    } as $valid

    precondition ($valid == true) {
      error_type = "accessdenied"
      error = "Invalid credentials"
    }

    db.get "workspace" {
      field_name = "id"
      field_value = $user.default_workspace_id
    } as $workspace

    precondition ($workspace != null) {
      error_type = "standard"
      error = "User has no workspace"
    }

    db.query "workspace_member" {
      where = $db.workspace_member.workspace_id == $workspace.id && $db.workspace_member.user_id == $user.id
      return = { type: "single" }
    } as $member

    var $role { value = "member" }
    conditional {
      if ($member != null) {
        var.update $role { value = $member.role }
      }
    }

    function.run "issue_token" {
      input = {
        user_id: $user.id,
        workspace_id: $workspace.id,
        role: $role
      }
    } as $token
  }
  response = {
    authToken: $token,
    user: { id: $user.id, name: $user.name, email: $user.email },
    workspace: { id: $workspace.id, name: $workspace.name }
  }
  guid = "qhEF2ZKtZqc0iKWrRReiTG2ko4I"
}
