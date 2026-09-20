"""Deterministic A -> B -> A timeline. Pose names never enter this player."""
import math

class MotionPlayer:
    def __init__(self,settings):
        self.settings=settings
        self.cursor=0.
        self.paused=True

    @property
    def half_period(self):
        return max(self.settings['target_interval'],6.64/self.settings['enter_response'],
                   6.64/self.settings['return_response'])

    @property
    def period(self):
        return 2*self.half_period

    @property
    def progress(self):
        return (self.cursor%self.period)/self.period

    @property
    def blend(self):
        half=self.half_period
        t=self.cursor%self.period
        entering=t<half
        duration=6.64/self.settings['enter_response' if entering else 'return_response']
        u=min(1.,(t if entering else t-half)/duration)
        smooth=u*u*u*(10+u*(-15+6*u))
        return smooth if entering else 1-smooth

    @property
    def phase(self):
        half=self.half_period
        t=self.cursor%self.period
        entering=t<half
        duration=6.64/self.settings['enter_response' if entering else 'return_response']
        if (t if entering else t-half)>=duration:
            return 'HOLD B' if entering else 'HOLD A'
        return 'A → B' if entering else 'B → A'

    def play(self):
        self.paused=False

    def pause(self):
        self.paused=True

    def toggle(self):
        self.paused=not self.paused

    def advance(self,dt,force=False):
        if not math.isfinite(dt) or dt<0:
            raise ValueError('Time step must be finite and nonnegative')
        if force or not self.paused:
            self.cursor=(self.cursor+dt)%self.period

    def seek(self,fraction):
        self.cursor=max(0.,min(.999999999,fraction))*self.period
        self.paused=True

    def reconfigure(self,settings):
        # Preserve the position in the cycle when motion settings are edited.
        phase=self.progress
        self.settings=settings
        self.cursor=phase*self.period

