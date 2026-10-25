path = r'C:\Users\bhagy\job-agent\skills\linkedin_outreach.md'
with open(path, encoding='utf-8') as f:
    s = f.read()
s2 = s.replace('React/Node', 'Java/SQL and GCP')
with open(path, 'w', encoding='utf-8') as f:
    f.write(s2)
print('done')
