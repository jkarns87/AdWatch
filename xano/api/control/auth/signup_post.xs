query "auth/signup" verb=POST {
  api_group = "control"
  description = "Create a user and their first workspace; returns an authToken with a workspace_id claim"
  input {
    text name filters=trim
    email email filters=trim|lower
    text password filters=min:8|max:128 {
      sensitive = true
    }
    text workspace_name? filters=trim
  }
  stack {
    db.query "user" {
      where = $db.user.email == $input.email
      return = { type: "exists" }
    } as $exists

    precondition ($exists == false) {
      error_type = "inputerror"
      error = "An account with this email already exists"
    }

    db.add "user" {
      data = {
        name: $input.name,
        email: $input.email,
        password: $input.password
      }
    } as $user

    var $ws_name { value = $input.workspace_name }
    conditional {
      if ($ws_name == null || $ws_name == "") {
        var.update $ws_name { value = $input.name ~ "'s workspace" }
      }
    }

    db.add "workspace" {
      data = {
        name: $ws_name,
        owner_id: $user.id,
        plan: "free"
      }
    } as $workspace

    db.add "workspace_member" {
      data = {
        workspace_id: $workspace.id,
        user_id: $user.id,
        role: "owner"
      }
    }

    db.patch "user" {
      field_name = "id"
      field_value = $user.id
      data = { default_workspace_id: $workspace.id }
    }

    function.run "issue_token" {
      input = {
        user_id: $user.id,
        workspace_id: $workspace.id,
        role: "owner"
      }
    } as $token
  }
  response = {
    authToken: $token,
    user: { id: $user.id, name: $user.name, email: $user.email },
    workspace: { id: $workspace.id, name: $workspace.name }
  }
}
