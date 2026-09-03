query "auth/forgot_password" verb=POST {
  api_group = "control"
  description = "Email a single-use password reset link. Always answers the same way, whether or not the address has an account."
  input {
    email email filters=trim|lower
  }
  stack {
    db.query "user" {
      where = $db.user.email == $input.email
      output = { type: "single" }
    } as $user

    // No precondition on $user: a different response for a known address would let
    // anyone enumerate registered emails. The work below is skipped, the answer is not.
    conditional {
      if ($user != null) {
        // Split token. The selector is the lookup key and is stored in clear; the
        // verifier proves possession and is hashed by the password field type.
        security.create_uuid as $selector
        security.create_password {
          character_count = 48
          require_lowercase = true
          require_uppercase = true
          require_digit = true
          require_symbol = false
        } as $verifier

        // Outstanding tokens for this user are spent, so a second request invalidates
        // the first link rather than leaving several live at once.
        db.query "password_reset" {
          where = $db.password_reset.user_id == $user.id && $db.password_reset.used_at == null
          output = { type: "list" }
        } as $outstanding

        foreach ($outstanding as $old) {
          db.patch "password_reset" {
            field_name = "id"
            field_value = $old.id
            data = { used_at: "now" }
          }
        }

        db.add "password_reset" {
          data = {
            user_id: $user.id,
            selector: $selector,
            verifier: $verifier,
            expires_at: "now+1 hour"
          }
        }

        var $link {
          value = $env.DASHBOARD_URL ~ "/reset-password?token=" ~ $selector ~ "." ~ $verifier
        }

        util.send_email {
          to = $user.email
          subject = "Reset your AdWatch password"
          message = "Someone asked to reset the password for this AdWatch account.\n\nOpen this link within the next hour to choose a new one:\n\n" ~ $link ~ "\n\nThe link can be used once. If you did not ask for this, you can ignore this email — nothing has changed."
        }
      }
    }
  }
  response = {
    ok: true,
    message: "If that address has an account, a reset link is on its way."
  }
}
