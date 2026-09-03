query "auth/reset_password" verb=POST {
  api_group = "control"
  description = "Redeem a reset link and set a new password. Tokens are single-use and expire after an hour."
  input {
    text token filters=trim {
      description = "selector.verifier, as issued in the email link"
      sensitive = true
    }
    text password filters=min:8|max:128 {
      sensitive = true
    }
  }
  stack {
    var $parts { value = $input.token|split:"." }

    precondition ($parts|count == 2) {
      error_type = "inputerror"
      error = "That reset link is not valid"
    }

    var $selector { value = $parts[0] }
    var $verifier { value = $parts[1] }

    db.query "password_reset" {
      where = $db.password_reset.selector == $selector
      output = { type: "single" }
    } as $reset

    // One message for every failure mode — unknown, spent and expired are not
    // distinguished, so the endpoint cannot be used to probe which links exist.
    precondition ($reset != null) {
      error_type = "inputerror"
      error = "That reset link is not valid or has expired"
    }

    precondition ($reset.used_at == null) {
      error_type = "inputerror"
      error = "That reset link is not valid or has expired"
    }

    precondition ($reset.expires_at > "now") {
      error_type = "inputerror"
      error = "That reset link is not valid or has expired"
    }

    security.check_password {
      text_password = $verifier
      hash_password = $reset.verifier
    } as $ok

    precondition ($ok == true) {
      error_type = "inputerror"
      error = "That reset link is not valid or has expired"
    }

    db.get "user" {
      field_name = "id"
      field_value = $reset.user_id
    } as $user

    precondition ($user != null) {
      error_type = "inputerror"
      error = "That reset link is not valid or has expired"
    }

    db.patch "user" {
      field_name = "id"
      field_value = $user.id
      data = { password: $input.password }
    }

    // Spend the token before returning, so a replayed request fails.
    db.patch "password_reset" {
      field_name = "id"
      field_value = $reset.id
      data = { used_at: "now" }
    }
  }
  response = {
    ok: true,
    message: "Your password has been changed. Sign in with the new one."
  }
}
