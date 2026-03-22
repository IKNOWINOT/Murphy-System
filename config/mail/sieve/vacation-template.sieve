require ["vacation", "fileinto"];

# Vacation auto-reply template
# Copy this file to ~/sieve/vacation.sieve and activate with:
#   ln -sf ~/sieve/vacation.sieve ~/.dovecot.sieve
#
# Then customise the :subject and body below.

vacation
  :days 1
  :subject "Out of Office: ${VACATION_SUBJECT:-I am currently out of the office}"
  :addresses ["me@murphy.systems"]
  "Thank you for your email. I am currently out of the office and will return on ${RETURN_DATE:-Monday}.

If your matter is urgent, please contact admin@murphy.systems.

Best regards,
Murphy System Auto-Responder";
