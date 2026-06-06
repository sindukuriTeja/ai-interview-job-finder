from models import Session, Candidate
s = Session()
cs = s.query(Candidate).all()
print('candidates_count=', len(cs))
for c in cs:
    print(c.id, c.name, c.email)
s.close()