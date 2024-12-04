# -*- coding: utf-8 -*-
import RPi.GPIO as GPIO
import time
import os

GPIO.cleanup()
GPIO.setmode(GPIO.BCM)  # Utiliser la numerotation BCM (Broadcom)

# Configurer GPIO 14 comme entree
# GPIO.setup(14, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)  # Utiliser une resistance de pull-down
GPIO.setup(14, GPIO.IN)  # sans resistance de pull-down
GPIO.setup(21, GPIO.OUT, initial=GPIO.LOW)   # Utiliser le port 21 pour allumer la led verte

time.sleep(3) # Attendre 3s

duree = 3 # 300 duree de l'ecran actif en secondes (5 minutes)
veille = False
wait = 0

#os.system("DISPLAY=:0 xscreensaver --no-splash &") # ne fonctionne pas
try:
    while True:
        input_state = GPIO.input(14)  # Lire l'etat de la broche GPIO 14
        if input_state == GPIO.HIGH:
            wait = duree
            #os.system("echo avant if veille >> /tmp/veille_ecran.log")
            if veille:
               #os.system("echo mise en veille >> /tmp/veille_ecran.log")
               os.system("DISPLAY=:0 XAUTHORITY=~sonometre_listrac/.Xauthority xscreensaver-command --deactivate")
               veille = False
               GPIO.output(21,GPIO.HIGH)
               while (wait > 0):
                   wait -= 1
                   time.sleep(1)
                   input_state = GPIO.input(14)  # Lire l'etat de la broche GPIO 14
                   if input_state == GPIO.HIGH:
                       wait=duree
        else:
            if (veille == False):
              os.system("DISPLAY=:0 XAUTHORITY=~sonometre_listrac/.Xauthority xscreensaver-command --activate")
              veille = True
            GPIO.output(21,GPIO.LOW)
        time.sleep(1) # Attendre 1s


except KeyboardInterrupt:
    print("Programme de mise en veille interrompu par l'utilisateur")
#except Exception:
#    print("exception")

finally:
    GPIO.cleanup()  # Reinitialiser les parametres GPIO
