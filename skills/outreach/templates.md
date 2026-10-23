# Outreach templates (cold email + LinkedIn referral)

Every template here is a starting point, not a script to paste blind. The first line of the
personalization block must be true for that company. If you cannot write one true line about the
company, do not send the email.

Hard rules (checked before a draft is accepted):
- No em dashes, no en dashes. Plain hyphens only.
- Subject under 60 characters. Body under 120 words.
- One ask per email. Never both "call" and "referral".
- Plain text. No attachments, no images, no tracking pixel.
- Never invent a project, number, certificate or years of experience.
- Use only facts from `resume/master.json`.

Verified facts you may use:
- Final-year B.Tech CSE, JECRC University Jaipur, graduating 2027.
- Smart Commute: ride pooling web app, Java, JSP, Servlet, MySQL. Normalized 3NF schema, 5+ tables,
  zero data-integrity issues across 100+ test records, ~30% less bug-fix time.
- PathToSDE: system design roadmap, HTML, CSS, JavaScript, 25+ topics, local-storage progress.
- Google Cloud Associate Cloud Engineer (foundations).
- Class Representative for 60+ students.

Signature block (keep it short):
```
Bhagyansh Chandel
B.Tech CSE, JECRC University Jaipur (2027)
+91-6268228869 | linkedin.com/in/bhagyanshchandel | github.com/Bhagyansh07
```

---

## 1. Cold email to a founder or CTO (company size 1-30)

Subject options:
- `Fresher full stack engineer for {{company}}`
- `Built a booking app in Java and MySQL, can I help {{company}}?`
- `{{company}} + one final-year CSE student`

Body:
```
Hi {{first_name}},

I am a final-year CSE student at JECRC University Jaipur. I build full stack products, mostly Java,
MySQL and JavaScript.

{{personal_line}} That is why {{company}} stood out to me.

For my last project I built a ride pooling app with a 3NF MySQL schema, session auth and form
validation, and kept zero data-integrity issues across 100+ test records. I also built PathToSDE, a
system design roadmap used by students in my college.

Is your team open to a fresher full stack engineer this quarter?

Bhagyansh Chandel
B.Tech CSE, JECRC University Jaipur (2027)
+91-6268228869 | linkedin.com/in/bhagyanshchandel | github.com/Bhagyansh07
```

`{{personal_line}}` examples (pick one that is actually true):
- `I used your API for a college project and the docs were the cleanest I have worked with.`
- `I saw your launch post about {{product}} and tried it the same day.`
- `Your engineering blog on {{topic}} changed how I structure my own projects.`

---

## 2. Cold email to an HR or talent head (from the recruiter sheet)

These people get a lot of mail. Keep it to the point and make the role match obvious.

Subject options:
- `Fresher full stack engineer, JECRC 2027, CGPA 9.25`
- `Application for entry level software engineer roles at {{company}}`
- `Final-year CSE student interested in {{company}}`

Body:
```
Hi {{first_name}},

I am a final-year B.Tech CSE student at JECRC University Jaipur, graduating in 2027, CGPA 9.25.

I am looking for an entry level software engineer role. My strongest work is backend and full stack:
a Java, JSP and MySQL ride pooling app with a normalized 3NF schema, and a JavaScript system design
roadmap with 25+ topics. I am also a Google Cloud Associate Cloud Engineer (foundations).

{{personal_line}}

Could you point me to the right person or the right opening on your team?

Bhagyansh Chandel
B.Tech CSE, JECRC University Jaipur (2027)
+91-6268228869 | linkedin.com/in/bhagyanshchandel | github.com/Bhagyansh07
```

Never send this to a BPO, staffing or manpower company. Those inboxes exist to sell you a job, not
to hire you.

---

## 3. Cold email to a JECRC alumnus

Subject: `JECRC alumnus here, quick question about {{company}}`

Body:
```
Hi {{first_name}},

I am a final-year CSE student at JECRC, graduating in 2027. I found you through the JECRC alumni
network on LinkedIn.

{{personal_line}}

I am trying to break into backend and full stack work. My last project was a ride pooling app in
Java, JSP and MySQL, and I built a system design roadmap in JavaScript that students in my college
now use.

Would you be open to a 10 minute call about how your team hires freshers?

Bhagyansh Chandel
B.Tech CSE, JECRC University Jaipur (2027)
+91-6268228869 | linkedin.com/in/bhagyanshchandel | github.com/Bhagyansh07
```

---

## 4. Follow-up 1 (send 4 working days later, same thread)

```
Hi {{first_name}},

Just bringing this back to the top of your inbox. I am still interested in an entry level software
role at {{company}}.

One quick update since my last email: {{one_new_true_thing}}.

If this is not your area, a one line pointer to the right person would help a lot.

Bhagyansh
```

Do not send a follow-up if the first email bounced. Mark it `failed` and move on.

---

## 5. Follow-up 2 (final, 7 days after follow-up 1)

```
Hi {{first_name}},

I will stop here so I am not adding noise. If a fresher opening opens up at {{company}} later, I
would be glad to apply.

Thanks for your time.

Bhagyansh
```

After this, mark the contact `skipped` and never email that company again.

---

## 6. LinkedIn referral DM (only after the connection request is accepted)

```
Hi {{first_name}}, thanks for connecting.

I am a final-year CSE student at JECRC, graduating 2027. I am applying for {{role}} at {{company}}.

Before I apply, would you be comfortable referring me internally? I can send my resume and the job
link in one message, and I will not ask you to chase anyone.

Either way, good to connect.
```

If they say yes:
```
Thank you. Here is the link: {{job_url}}
Resume attached. My strongest work is a Java, JSP and MySQL ride pooling app with a normalized 3NF
schema, plus a JavaScript system design roadmap with 25+ topics.
```

If they say no or do not reply, do not ask twice.

---

## 7. LinkedIn referral ask to an engineer (no job link yet)

```
Hi {{first_name}}, I am a final-year CSE student at JECRC.

I am trying to understand what {{company}} looks for in fresher backend engineers. Would you answer
two quick questions here, no call needed?

1. Which stack does your team actually use day to day?
2. Is a referral useful, or should I apply through the portal only?
```

This gets replies because it is small, specific and easy to answer.

---

## 8. Recruiter reply handling (never auto-reply)

When a recruiter replies:
1. `cold_email.py mark --id <id> --status replied`
2. Send the reply text to Bhagyansh on Telegram with the sender, company and the exact question.
3. Do not answer it yourself. AGENTS.md rule 2.

---

## Personalization line bank (use only what is true)

- `I read your engineering post on {{topic}} and it matched a problem I hit in my own project.`
- `I have been using {{product}} for {{use_case}} and noticed {{specific_detail}}.`
- `I saw {{company}} is hiring in {{city}} and I am based in Jaipur, open to relocating.`
- `I saw the {{funding_round}} news and assumed the engineering team is growing.`
- `Your careers page lists {{stack}} and that is the stack I have been building in.`

If none of these is true for a company, skip that company. A generic first line is worse than no
email.
