import env.server.app
import smm.smm

smm = smm.smm.SMM("predicates", visibility="O99", agent="A0")
env.server.app.run(_smm=smm)