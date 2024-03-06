import env.server.app
import smm.smm

smm = smm.smm.SMM("predicates", visibility="O99")
env.server.app.run(_smm=smm)