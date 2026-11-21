import io, os, sys, tempfile
os.environ.setdefault('CLAVERATS_DATA_DIR', tempfile.mkdtemp(prefix='claverats_test_'))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def make_cv_pdf(name="Jean Mukendi", email="jean.mukendi@example.com", link="https://www.linkedin.com/in/jean-mukendi"):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    y = 800
    for line in [name, "Developpeur Python", "Tel : 0812345678  " + email, "Kinshasa",
                 "EXPERIENCE", "Mars 2020 - Juin 2022", "Developpeur Backend", "Societe Alpha Technologies",
                 "- Developpement d'API Flask et SQL pour la gestion des clients",
                 "2023 - Present", "Ingenieur Logiciel", "Beta Solutions",
                 "- Mise en place de Docker et Git pour le deploiement continu",
                 "FORMATION", "Licence en informatique 2019", "COMPETENCES", "Python, SQL, Docker, Git, Flask, JavaScript",
                 "LANGUES", "Francais, Anglais"]:
        c.drawString(60, y, line)
        y -= 22
    c.linkURL(link, (60, 600, 200, 620))
    c.save()
    return buf.getvalue()

JOB = ("Entreprise : Alpha Corp\nOffre d'emploi CDI Developpeur Python Kinshasa.\n"
       "Competences : Python, SQL, Docker, Git, Kubernetes, AWS. 3 ans d'experience. Licence. Francais.\n"
       "Candidature : rh@alpha-corp.com")


def client():
    import app as A
    A.app.config["TESTING"] = True
    c = A.app.test_client()
    tok = c.get("/api/svc/csrf").get_json()["token"]
    return c, {"X-CSRF-Token": tok}
