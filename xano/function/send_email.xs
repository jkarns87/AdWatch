function "send_email" {
  description = "Send one transactional email through Resend. Xano has no native email delivery — util.send_email parses but delivers nothing — so every send goes through this one function."
  input {
    email to
    text subject
    text message
  }
  stack {
    // Both are set in the Xano environment, not Fly. RESEND_FROM must be an address
    // on a domain verified with Resend, or delivery is refused for anyone other than
    // the account holder.
    api.request {
      url = "https://api.resend.com/emails"
      method = "POST"
      params = {
        from: $env.RESEND_FROM,
        to: [$input.to],
        subject: $input.subject,
        text: $input.message
      }
      headers = ["Authorization: Bearer " ~ $env.RESEND_API_KEY, "Content-Type: application/json"]
      timeout = 10
    } as $res

    var $ok { value = $res.response.status >= 200 && $res.response.status < 300 }
  }
  response = { ok: $ok, status: $res.response.status }
  guid = "AvAV_pnYANSVQQ12Q72xLB62VTQ"
}
