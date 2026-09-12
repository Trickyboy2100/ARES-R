# ARES-R Skill Library S0 Reference Audit

Status: design-only research, 2026-09-12. No external implementation is copied. No skill is commissioned by this document.

## Method and scope

The seven requested repositories were shallow-cloned outside ARES-R and inspected at the pinned revisions below. XDL was inspected from its official GitLab repository and official standard documentation. ARES-R and legacy ARES were consulted only for integration constraints, never as the source of the taxonomy.

| Reference | Revision | License | Primary evidence inspected |
|---|---:|---|---|
| PyLabRobot | `9714d99e3cef` | MIT | `pylabrobot/resources/resource.py`, `deck.py`, `resource_holder.py`; `legacy/machines/machine.py`, `backend.py`; device frontends/backends |
| Stretch AI | `6272b28e3ff7` | Apache-2.0 | `src/stretch/core/task.py`; `agent/base/managed_operation.py`; `agent/task/pickup/pickup_task.py`; `agent/task/llm_plan/llm_plan_executor.py`; `docs/adding_a_new_task.md` |
| HomeRobot | `ede6a67a2d0c` | MIT | `agent/ovmm_agent/ovmm_agent.py`, `pick_and_place_agent.py`; hardware and Habitat abstract agents/environments |
| MoveIt Task Constructor | `f527048b3db1` | BSD-3-Clause | `core/include/.../stage.h`, `container.h`; `demo/src/pick_place_task.cpp`; task execution action/messages |
| BehaviorTree.CPP | `9b63b505983f` | MIT | `basic_types.h`, `tree_node.h`, `action_node.h`; sequence/fallback/parallel/retry nodes; blackboard |
| Isaac ROS Manipulation | `f5c47880e42e` | Apache-2.0 | orchestration `base_action.py`; perception/motion subtrees; `attach_object.py`; mock servers; bringup launch/config |
| RoboCasa | `4f8a2980def7` | MIT | atomic task index; atomic kitchen environments; fixture models; composite tasks; success predicates/tests |
| XDL/Chemputer | `6d60e8da7218` | AGPL-3.0 with stated non-profit/open-source considerations; legal review required before code reuse | `xdl/steps/core/*`; `xdl/utils/xdl_base.py`; `xdl/platforms/abstract_platform.py`; standard steps and blueprints docs |

License conclusion: architecture ideas and vocabulary may be studied, but this S0 imports no code. XDL's repository license wording is more restrictive than the permissive licenses in the other references; therefore ARES-R should adopt concepts, not implementation, unless separately cleared.[^xdl-license]

## Cross-reference answers

### PyLabRobot

1. **Smallest reusable unit:** an async device operation exposed by a device frontend; it receives concrete `Resource` objects, while a backend performs vendor-specific I/O.
2. **Layering:** user operation → device frontend/state tracking → abstract backend → vendor backend. It is not a general task executive.
3. **Workspace/resources:** `Resource` is a stable-name hierarchical geometry tree with parent/children, local transform, dimensions, category/model/barcode/metadata and serialization. Decks and holders specialize containment.[^plr-resource]
4. **Conditions/effects/success:** frontend validation and resource state updates are strong; declarative preconditions/effects and uniform success criteria are not first-class.
5. **Status:** primarily awaited calls/exceptions, not a universal RUNNING/SUCCESS/FAILURE protocol.
6. **Recovery:** device-specific; no general fallback graph.
7. **Simulation/hardware:** backend substitution, including recording/chatterbox or mock backends, preserves frontend calls.[^plr-backend]
8. **LLM surface:** none designed; raw frontend methods would be too broad to expose directly.
9. **Lab resources:** strongest reference: deck/holder/slot/resource identity and nested placement are explicit.
10. **ARES-R decision:** adopt stable resource identity, hierarchy, relative transforms and capability backend injection. Reject merging semantic inventory with planning geometry, and reject exceptions as normal skill outcomes.

### Stretch AI

1. **Smallest reusable unit:** `Operation`, with `can_start()`, `run()` and `was_successful()`.
2. **Layering:** Operations are connected into a `Task`; pickup assembles search, navigation, pregrasp, grasp and place operations.[^stretch-task]
3. **Workspace/resources:** semantic voxel/instance memory and agent fields, not a laboratory resource graph.
4. **Conditions/effects/success:** methods exist but are imperative and operation-specific.
5. **Status:** operation strings plus blocking task execution; success is boolean.
6. **Recovery:** explicit `on_success`, `on_failure`, `on_cannot_start`, self-retry and failure limits.
7. **Simulation/hardware:** abstract robot client helps, but task code can still depend heavily on the concrete agent/world memory.
8. **LLM surface:** LLM plans map to a limited action vocabulary, which is directionally useful; executing generated code/plans without schema and policy gates is not sufficient for ARES-R.[^stretch-llm]
9. **Lab resources:** absent beyond object/receptacle instances.
10. **ARES-R decision:** adopt operation graph readability and distinct cannot-start vs failed outcomes. Replace blocking execution, booleans and free-form LLM plans with typed invocation/result, cancellation, locks and policy validation.

### HomeRobot

1. **Smallest reusable unit:** a policy/agent skill producing actions per observation tick.
2. **Layering:** long-horizon mobile manipulation is decomposed into navigation-to-object, gaze, pick, navigation-to-receptacle, gaze and place; a state machine selects specialized policies.[^home-ovmm]
3. **Workspace/resources:** semantic maps, object/receptacle categories and observations; not holder/slot/sample inventory.
4. **Conditions/effects/success:** transitions rely on observations such as `prev_grasp_success` and policy stop signals, rather than a uniform contract.
5. **Status:** action-at-each-tick and state-machine phase; termination commonly uses STOP.
6. **Recovery:** state transitions and fall-wait exist, but failure taxonomy and transactional effects are limited.
7. **Simulation/hardware:** shared agent/action abstractions span Habitat simulation and hardware environments.
8. **LLM surface:** not the core strength of the audited OVMM path.
9. **Lab resources:** object and receptacle goals, not laboratory lineage/occupancy.
10. **ARES-R decision:** adopt the separation of mobile approach, perception orientation, manipulation and verification, and the common observation/action interface. Reject monolithic agent mutable state as system-of-record.

### MoveIt Task Constructor (MTC)

1. **Smallest reusable unit:** planning `Stage`; generator, propagator and connector stages exchange interface states.
2. **Layering:** Task → serial/alternative/fallback/merger containers → stages → planners/trajectories.[^mtc-stage]
3. **Workspace/resources:** PlanningScene/RobotState and properties, not semantic laboratory inventory.
4. **Conditions/effects/success:** feasibility is encoded through stage input/output states and solutions/failures; scene-changing stages model attach/detach and collision changes.
5. **Status:** planning solutions and failures, with introspection/statistics; execution is a separate action.
6. **Recovery:** planning alternatives and ordered fallbacks; this does not by itself provide runtime recovery.
7. **Simulation/hardware:** plans against robot/planning models; execution backend remains separable.
8. **LLM surface:** none; individual stages and poses must not be exposed as unrestricted LLM tools.
9. **Lab resources:** none beyond collision objects.
10. **ARES-R decision:** adopt explicit `SkillPlan` phase decomposition, alternative planners, immutable scene binding and attachment transitions. Do not equate MTC PlanningScene with LabWorkspace, or planning success with task success.[^mtc-pick]

### BehaviorTree.CPP

1. **Smallest reusable unit:** typed-port tree node; `StatefulActionNode` is the preferred asynchronous action form.
2. **Layering:** leaf action/condition → decorator/control node → subtree → behavior tree.
3. **Workspace/resources:** typed blackboard ports and remapping, not a persistent resource ontology.
4. **Conditions/effects/success:** pre/post scripts and condition nodes; effects remain leaf-defined.
5. **Status:** IDLE/RUNNING/SUCCESS/FAILURE (plus SKIPPED), with explicit halt/cancellation for running actions.[^bt-status]
6. **Recovery:** sequence, fallback, retry and threshold parallel are composable and bounded when configured correctly.[^bt-recovery]
7. **Simulation/hardware:** leaf implementations can be replaced while trees remain stable.
8. **LLM surface:** XML/tree construction is too powerful for direct exposure; a registry of approved leaves/subtrees is safer.
9. **Lab resources:** blackboard dataflow only; no occupancy, lineage or stable sample identity.
10. **ARES-R decision:** adopt lifecycle semantics, cooperative cancellation, bounded decorators and explicit dataflow. Reject an untyped/global blackboard as truth, infinite retries and unrestricted parallelism around shared robot resources.

### Isaac ROS Manipulation

1. **Smallest reusable unit:** a ROS action/service-backed behavior.
2. **Layering:** perception and motion behaviors → subtrees → workflow behavior tree → ROS action/service servers and accelerated nodes.
3. **Workspace/resources:** blackboard object cache, TF, meshes and planning/collision state; no lab resource graph.
4. **Conditions/effects/success:** server availability, blackboard inputs and action outcomes; attach modifies collision representation.[^isaac-attach]
5. **Status:** py_trees RUNNING/SUCCESS/FAILURE backed by explicit action states.
6. **Recovery:** runtime server retry with timeout plus tree decorators; workflow status/report generation is separate.
7. **Simulation/hardware:** launch/config variants and server boundaries permit mock/sim/real substitution; mock servers are present.
8. **LLM surface:** none directly; ROS graph access would be too broad.
9. **Lab resources:** object cache only.
10. **ARES-R decision:** adopt action/service boundaries, mock servers, perception/motion concurrency where resources are disjoint, and explicit attach/detach orchestration. Reject treating a continuously updated blackboard as a coherent planning snapshot.[^isaac-bt]

### RoboCasa

1. **Smallest reusable unit:** benchmark atomic task/environment with reset distribution and `_check_success()` predicate; it is closer to a training task than a reusable production action.
2. **Layering:** 65 atomic tasks across fixture interactions/pick-place/navigation, then composite household tasks.[^robocasa-atomic]
3. **Workspace/resources:** fixtures, articulated joints/handles, regions, objects and randomized placements in MuJoCo.
4. **Conditions/effects/success:** initial-state generation plus task-specific predicates such as object-in-region or door-joint threshold.
5. **Status:** episodic reward/success, not runtime RUNNING lifecycle.
6. **Recovery:** policies learn or retry externally; no production recovery contract.
7. **Simulation/hardware:** simulation-first; no hardware backend contract.
8. **LLM surface:** language instructions provide useful semantic coverage but are not a safety boundary.
9. **Lab resources:** fixtures and objects, but no sample provenance/consumables/occupancy transactions.
10. **ARES-R decision:** adopt coverage evidence, affordance/state predicates and success-predicate thinking. Merge device-specific `OpenMicrowave/OpenOven/...` into generic `open_door(resource)` driven by resource affordances. Do not copy benchmark task classes or assume sim success transfers to real commissioning.

### XDL / Chemputer

1. **Smallest reusable unit:** typed, hardware-independent `Step`; abstract/dynamic steps expand into lower-level steps.
2. **Layering:** procedure/blueprint → semantic standard step → platform compilation → base/device steps → controller.[^xdl-overview]
3. **Workspace/resources:** hardware component graph plus vessels/reagents; good process semantics, less suitable for free-space mobile geometry.
4. **Conditions/effects/success:** typed properties, limits, defaults, sanity checks and compilation; effects/success are less uniformly declarative than ARES-R requires.
5. **Status:** synchronous/async execution classes and monitoring, not the exact BT status model.
6. **Recovery:** procedure constructs and platform-specific handling; not a complete general robotics recovery system.
7. **Simulation/hardware:** hardware-independent procedures compile against a platform/graph, the strongest semantic/backend separation in this audit.[^xdl-compile]
8. **LLM surface:** a standard step vocabulary and typed parameters are a strong safe API basis; natural-language translation still requires validation.
9. **Lab resources:** vessels, reagents, hardware components and typed quantities are strong; holder/slot and mobile zones need extension.
10. **ARES-R decision:** adopt typed units, semantic steps, reusable protocol templates and platform compilation. Do not copy code, inherit the AGPL implementation, or make XDL's fluidic graph the robot's geometric world model.

## Comparative synthesis

| Concern | Strongest evidence | ARES-R synthesis |
|---|---|---|
| Lab resource identity/hierarchy | PyLabRobot | `LabWorkspace/ResourceGraph`, stable IDs, containment and occupancy |
| Typed experimental semantics | XDL | L3 skills and L4 protocols use typed units and semantic resources |
| Manipulation planning decomposition | MTC | `SkillPlan.steps`, snapshot-bound planning and attach/detach effects |
| Runtime lifecycle/recovery | BehaviorTree.CPP | explicit PENDING/RUNNING/terminal states, cancel, bounded retry/fallback |
| Mobile manipulation hierarchy | HomeRobot + Stretch AI | navigation/observe/approach/manipulate/verify remain distinct |
| Perception/planning/action boundaries | Isaac ROS | capability providers behind typed service-like interfaces |
| Coverage and affordances | RoboCasa | generic articulation and device interaction skills with predicate verification |

### Important disagreements

- **Exceptions vs results:** PyLabRobot and many ROS/Python paths use exceptions for operation faults; ARES-R uses typed `SkillResult` for expected business failure and reserves exceptions for bugs/corruption.
- **Mutable live world vs snapshot:** Stretch/HomeRobot/Isaac workflows commonly read mutable agent/blackboard state; ARES-R planning and execution bind to immutable `SceneSnapshot` plus digests.
- **Task atomicity:** RoboCasa calls whole benchmark episodes “atomic”; MTC calls individual feasibility transformations stages; XDL steps can expand. ARES-R defines a skill by stable semantic intent with independently verifiable effect—not by code size or episode count.
- **Parallelism:** BT/Isaac make concurrency easy; ARES-R permits it only after deterministic resource/zone lock analysis.
- **Backend equivalence:** PyLabRobot/XDL favor one semantic call across platforms; ARES-R adopts this and rejects `MockPickSkill/IsaacPickSkill/RealPickSkill` class proliferation.
- **Resource model:** planning scenes and voxel maps describe geometry, while deck/component graphs describe semantics. ARES-R keeps both and joins them by stable ID.

## Adopt / reject summary

Adopt: immutable identity, resource containment, typed parameters/units, capability-provider injection, explicit planning stages, async lifecycle, cancellation, bounded recovery, state-predicate verification, attachment semantics, mock/sim/real parity at the provider boundary, and a curated LLM tool subset.

Reject: raw actuator tools for LLMs; direct `Epic → cuRobo`; coordinate-only public APIs; mutable blackboard as truth; device-specific skill explosion; infinite retry; planning-success-as-task-success; three separate semantic skills for mock/sim/real; and merging resource inventory into WorldModel.

## ARES integration evidence (not taxonomy sources)

- ARES-R `src/ares_r/world/{robot_state,scene_snapshot,world_model,validity}.py` already provides immutable robot/observation/environment/snapshot contracts and invalidation.
- ARES-R `src/ares_r/{adapters,motion}/` provides the future Real capability-provider seams; these are not changed in S0.
- Legacy ARES `core/planning.py`, `core/gripper.py`, `core/scene_utils.py` and `isaac_sim/` demonstrate possible Isaac-side planning, gripper and scene adapters. They do not determine skill names or layers.

## Sources

[^plr-resource]: [PyLabRobot `Resource` hierarchy and serialization](https://github.com/PyLabRobot/pylabrobot/blob/9714d99e3cef/pylabrobot/resources/resource.py) and [`ResourceHolder`](https://github.com/PyLabRobot/pylabrobot/blob/9714d99e3cef/pylabrobot/resources/resource_holder.py).
[^plr-backend]: [PyLabRobot machine frontend](https://github.com/PyLabRobot/pylabrobot/blob/9714d99e3cef/pylabrobot/legacy/machines/machine.py) and [backend interface](https://github.com/PyLabRobot/pylabrobot/blob/9714d99e3cef/pylabrobot/legacy/machines/backend.py).
[^stretch-task]: [Stretch AI Operation/Task contract](https://github.com/hello-robot/stretch_ai/blob/6272b28e3ff7/src/stretch/core/task.py) and [pickup task composition](https://github.com/hello-robot/stretch_ai/blob/6272b28e3ff7/src/stretch/agent/task/pickup/pickup_task.py).
[^stretch-llm]: [Stretch AI guide for adding an LLM task](https://github.com/hello-robot/stretch_ai/blob/6272b28e3ff7/docs/adding_a_new_task.md) and [LLM plan executor](https://github.com/hello-robot/stretch_ai/blob/6272b28e3ff7/src/stretch/agent/task/llm_plan/llm_plan_executor.py).
[^home-ovmm]: [HomeRobot OVMM skill selector](https://github.com/facebookresearch/home-robot/blob/ede6a67a2d0c/src/home_robot/home_robot/agent/ovmm_agent/ovmm_agent.py) and [pick/place state machine](https://github.com/facebookresearch/home-robot/blob/ede6a67a2d0c/src/home_robot/home_robot/agent/ovmm_agent/pick_and_place_agent.py).
[^mtc-stage]: [MTC stage interfaces](https://github.com/moveit/moveit_task_constructor/blob/f527048b3db1/core/include/moveit/task_constructor/stage.h) and [container semantics](https://github.com/moveit/moveit_task_constructor/blob/f527048b3db1/core/include/moveit/task_constructor/container.h).
[^mtc-pick]: [MTC pick/place stage decomposition and planning-scene attachment](https://github.com/moveit/moveit_task_constructor/blob/f527048b3db1/demo/src/pick_place_task.cpp).
[^bt-status]: [BehaviorTree.CPP statuses](https://github.com/BehaviorTree/BehaviorTree.CPP/blob/9b63b505983f/include/behaviortree_cpp/basic_types.h), [typed ports/preconditions](https://github.com/BehaviorTree/BehaviorTree.CPP/blob/9b63b505983f/include/behaviortree_cpp/tree_node.h), and [stateful async actions](https://github.com/BehaviorTree/BehaviorTree.CPP/blob/9b63b505983f/include/behaviortree_cpp/action_node.h).
[^bt-recovery]: [BehaviorTree.CPP Retry](https://github.com/BehaviorTree/BehaviorTree.CPP/blob/9b63b505983f/include/behaviortree_cpp/decorators/retry_node.h), [Fallback](https://github.com/BehaviorTree/BehaviorTree.CPP/blob/9b63b505983f/include/behaviortree_cpp/controls/fallback_node.h), and [Parallel](https://github.com/BehaviorTree/BehaviorTree.CPP/blob/9b63b505983f/include/behaviortree_cpp/controls/parallel_node.h).
[^isaac-attach]: [Isaac ROS attach-object behavior](https://github.com/NVIDIA-ISAAC-ROS/isaac_ros_manipulation/blob/f5c47880e42e/isaac_ros_manipulation_orchestration/isaac_ros_manipulation_orchestration/behaviors/motion_behaviors/attach_object.py) and [base ROS action lifecycle](https://github.com/NVIDIA-ISAAC-ROS/isaac_ros_manipulation/blob/f5c47880e42e/isaac_ros_manipulation_orchestration/isaac_ros_manipulation_orchestration/behaviors/base_action.py).
[^isaac-bt]: [Isaac ROS multi-object pick/place tree](https://github.com/NVIDIA-ISAAC-ROS/isaac_ros_manipulation/blob/f5c47880e42e/isaac_ros_manipulation_pick_and_place/isaac_ros_manipulation_pick_and_place/behavior_trees/multi_object_pick_and_place_bt.py).
[^robocasa-atomic]: [RoboCasa atomic task index](https://github.com/robocasa/robocasa/blob/4f8a2980def7/docs/atomic_tasks/atomic_task_index.js), [door tasks](https://github.com/robocasa/robocasa/blob/4f8a2980def7/robocasa/environments/kitchen/atomic/kitchen_doors.py), and [fixture model](https://github.com/robocasa/robocasa/blob/4f8a2980def7/robocasa/models/fixtures/cabinets.py).
[^xdl-overview]: [Official XDL 2.0 standard](https://croningroup.gitlab.io/chemputer/xdl/standard/index.html), [steps overview](https://croningroup.gitlab.io/chemputer/xdl/standard/steps_overview.html), and [typed-unit base](https://croningroup.gitlab.io/chemputer/xdl/development/xdl_base.html).
[^xdl-compile]: [Official XDL compile workflow](https://croningroup.gitlab.io/chemputer/xdl/usage/compile_xdl.html) and [blueprints](https://croningroup.gitlab.io/chemputer/xdl/standard/xdl_blueprints.html).
[^xdl-license]: [XDL repository license at audited revision](https://gitlab.com/croningroup/chemputer/xdl/-/blob/6d60e8da7218a589b9c8715a239956601b17cd07/LICENSE.txt).
