import unittest

from ares_r.manipulation.skill_adapters import (ExecutionSkills,ManipulationSkills,
                                                 NavigationSkills,ObservationSkills)


class Recorder:
    def __init__(self): self.calls=[]
    def navigate(self,*a): self.calls.append(("navigate",a));return "NAV"
    def move_relative(self,*a,**k): self.calls.append(("relative",a,k));return "REL"
    def capture(self,*a,**k): self.calls.append(("capture",a,k));return "OBS"
    def plan(self,*a): self.calls.append(("plan",a));return "PLAN"
    def attach(self,*a): self.calls.append(("attach",a))
    def detach(self,*a): self.calls.append(("detach",a))
    def authorize(self,**k): self.calls.append(("authorize",k));return "PERMIT"


class SkillAdapterTests(unittest.TestCase):
    def test_navigation_and_observation_delegate(self):
        value=Recorder()
        self.assertEqual(NavigationSkills(value).go_to_station("PICK"),"NAV")
        self.assertEqual(NavigationSkills(value).registered_relative(.1,0,0),"REL")
        self.assertEqual(ObservationSkills(value).capture_scene_and_detect_resource("out"),"OBS")

    def test_every_free_space_manipulation_uses_same_service(self):
        motion=Recorder();world=Recorder()
        skills=ManipulationSkills(motion,world,lambda *_:None,lambda *_:None)
        for operation in (skills.move_free,skills.lift,skills.move_above_place,skills.retreat):
            self.assertEqual(operation("REQUEST"),"PLAN")
        self.assertEqual([row[0] for row in motion.calls],["plan"]*4)

    def test_attachment_and_execution_are_thin_transitions(self):
        world=Recorder();attached=type("A",(),{"object_id":"tray","source_revision":"OBS"})()
        skills=ManipulationSkills(Recorder(),world,lambda *_:None,lambda *_:None)
        self.assertEqual(skills.grasp("right",attached)["transition"],"ATTACHED")
        self.assertEqual(skills.release("right")["transition"],"DETACHED")
        kernel=Recorder();execution=ExecutionSkills(kernel,lambda p,t:(p,t))
        self.assertEqual(execution.authorize(x=1),"PERMIT")
        self.assertEqual(execution.execute_trajectory("P","T"),("P","T"))


if __name__ == "__main__": unittest.main()
