from xbox360controller import Xbox360Controller
import pygame

class unicode:
    def isprintable():
        pass

def button_press(key):
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode))

controller = Xbox360Controller()

def init():
    controller.button_start.when_pressed = lambda button: button_press(pygame.K_SPACE)
    controller.button_a.when_pressed = lambda button: button_press(pygame.K_SPACE)
    controller.button_b.when_pressed = lambda button: button_press(pygame.K_SPACE)
    controller.button_x.when_pressed = lambda button: button_press(pygame.K_SPACE)
    controller.button_y.when_pressed = lambda button: button_press(pygame.K_SPACE)
