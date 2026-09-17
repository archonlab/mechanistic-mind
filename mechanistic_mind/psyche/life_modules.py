from __future__ import annotations

from copy import deepcopy
from math import sqrt
from typing import Any

from mechanistic_mind.agent import Action
from .contracts import PsycheActionCandidate, PsycheContext, PsycheModule, PsycheOutput, PsycheSelection, PsycheStage, PsycheUpdate
from .modules import GoalMaintenanceModule, HabitModule, PerceptionModule, SelfModelModule


def _numeric_consequence(context: PsycheContext) -> dict[str, float] | None:
    value = context.observation.data.get("last_consequence")
    if not isinstance(value, dict):
        return None
    return {str(k): float(v) for k, v in value.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}


def _position(value: Any) -> tuple[int, int] | None:
    if isinstance(value, (list, tuple)) and len(value) == 2 and all(isinstance(v, int) for v in value):
        return int(value[0]), int(value[1])
    return None


def _move_destination(action: str) -> tuple[int, int] | None:
    if not action.startswith("MOVE:"):
        return None
    try:
        x, y = action.split(":", 1)[1].split(",", 1)
        return int(x), int(y)
    except Exception:
        return None


def _manhattan(a: tuple[int, int], b: tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _homeostatic_gain(consequence: dict[str, float], internal: dict[str, Any], goals: dict[str, Any]) -> float:
    dimensions = (
        ("energy", "energy_delta", "energy_setpoint", "energy_weight", "energy_critical", "low"),
        ("hydration", "hydration_delta", "hydration_setpoint", "hydration_weight", "hydration_critical", "low"),
        ("fatigue", "fatigue_delta", "fatigue_setpoint", "fatigue_weight", "fatigue_critical", "high"),
    )
    total = 0.0
    for state_key, delta_key, target_key, weight_key, critical_key, danger_side in dimensions:
        current = float(internal.get(state_key, 0.0))
        target = float(goals.get(target_key, current))
        weight = float(goals.get(weight_key, 1.0))
        after_value = _clamp01(current + consequence.get(delta_key, 0.0))
        before_error = (current - target) ** 2
        after_error = (after_value - target) ** 2
        total += (before_error - after_error) * weight
        critical = goals.get(critical_key)
        if critical is not None:
            critical = float(critical)
            if danger_side == "low":
                before_risk = max(0.0, critical - current)
                after_risk = max(0.0, critical - after_value)
            else:
                before_risk = max(0.0, current - critical)
                after_risk = max(0.0, after_value - critical)
            total += weight * 4.0 * (before_risk - after_risk)
    return total


class LifeInternalRegulationModule(PsycheModule):
    module_id = "PSY-REGULATION-LIFE-V01"; version = "0.2.1"; stage = PsycheStage.REGULATION
    def process(self, context: PsycheContext) -> PsycheOutput:
        internal = dict(context.state.internal)
        energy = float(internal.get("energy", 0.78)); hydration = float(internal.get("hydration", 0.78)); fatigue = float(internal.get("fatigue", 0.15)); progress = float(internal.get("progress", 0.0))
        consequence = _numeric_consequence(context)
        if consequence:
            energy += consequence.get("energy_delta", 0.0); hydration += consequence.get("hydration_delta", 0.0); fatigue += consequence.get("fatigue_delta", 0.0); progress += consequence.get("progress_delta", 0.0)
        energy = _clamp01(energy - 0.006); hydration = _clamp01(hydration - 0.009); fatigue = _clamp01(fatigue + 0.006)
        goals = context.state.goals
        errors = {"energy": abs(float(goals.get("energy_setpoint", energy)) - energy), "hydration": abs(float(goals.get("hydration_setpoint", hydration)) - hydration), "fatigue": abs(float(goals.get("fatigue_setpoint", fatigue)) - fatigue)}
        tension = sum(errors.values()) / len(errors)
        return PsycheOutput(updates=(PsycheUpdate("internal","energy",energy),PsycheUpdate("internal","hydration",hydration),PsycheUpdate("internal","fatigue",fatigue),PsycheUpdate("internal","progress",progress),PsycheUpdate("global_state","tension",tension)), signals={"energy":energy,"hydration":hydration,"fatigue":fatigue,"progress":progress,"errors":errors,"tension":tension})


class LifeAttentionModule(PsycheModule):
    module_id = "PSY-ATTENTION-LIFE-V01"; version = "0.2.1"; stage = PsycheStage.ATTENTION
    def process(self, context: PsycheContext) -> PsycheOutput:
        percept = context.state.percept.get("current", {}); percept = percept if isinstance(percept, dict) else {}
        selected = {k: deepcopy(percept[k]) for k in ("available_actions","position","visible_objects","last_action","last_consequence","context") if k in percept}
        return PsycheOutput(updates=(PsycheUpdate("attention","current",selected),PsycheUpdate("attention","capacity",6)), signals={"selected_keys":list(selected),"capacity":6})


class LifeOutcomeLearningModule(PsycheModule):
    module_id = "PSY-LEARNING-LIFE-V01"; version = "0.2.1"; stage = PsycheStage.LEARNING
    def process(self, context: PsycheContext) -> PsycheOutput:
        attended = context.state.attention.get("current", {}); attended = attended if isinstance(attended, dict) else {}
        action = attended.get("last_action"); consequence = attended.get("last_consequence"); models = deepcopy(context.state.learning.get("action_models", {}))
        if not isinstance(action, str) or not isinstance(consequence, dict):
            return PsycheOutput(signals={"updated_action":None,"model_count":len(models)})
        numeric = {str(k):float(v) for k,v in consequence.items() if isinstance(v,(int,float)) and not isinstance(v,bool) and k != "invalid_action"}
        if not numeric:
            return PsycheOutput(signals={"updated_action":None,"model_count":len(models)})
        record = deepcopy(models.get(action,{"count":0,"mean":{}})); count=int(record.get("count",0))+1; means=dict(record.get("mean",{}))
        for k,v in numeric.items():
            old=float(means.get(k,0.0)); means[k]=old+(v-old)/count
        models[action]={"count":count,"mean":means}
        return PsycheOutput(updates=(PsycheUpdate("learning","action_models",models),),signals={"updated_action":action,"sample_count":count,"means":means})


class LifeSpatialMemoryModule(PsycheModule):
    module_id = "PSY-MEMORY-LIFE-V01"; version = "0.2.1"; stage = PsycheStage.MEMORY
    def process(self, context: PsycheContext) -> PsycheOutput:
        memory=context.state.memory; episodes=list(deepcopy(memory.get("episodes",[]))); max_episodes=int(memory.get("max_episodes",64)); spatial=deepcopy(memory.get("spatial",{"visited":{},"objects":{}})); visited=dict(spatial.get("visited",{})); objects=dict(spatial.get("objects",{}))
        attended=context.state.attention.get("current",{}); attended=attended if isinstance(attended,dict) else {}; position=_position(attended.get("position"))
        if position is not None:
            key=f"{position[0]},{position[1]}"; visited[key]=int(visited.get(key,0))+1
        visible=attended.get("visible_objects")
        if isinstance(visible,list):
            for item in visible:
                if not isinstance(item,dict): continue
                object_id=str(item.get("id") or "").strip(); pos=_position(item.get("position"))
                if object_id and pos is not None:
                    objects[object_id]={"position":list(pos),"affordance":str(item.get("affordance") or "USE"),"last_seen_tick":context.tick}
        if attended.get("last_action") is not None and attended.get("last_consequence") is not None:
            episodes.append({"tick":context.tick,"position":list(position) if position else None,"action":attended.get("last_action"),"consequence":deepcopy(attended.get("last_consequence")),"visible_objects":deepcopy(visible if isinstance(visible,list) else [])}); episodes=episodes[-max_episodes:]
        return PsycheOutput(updates=(PsycheUpdate("memory","episodes",episodes),PsycheUpdate("memory","spatial",{"visited":visited,"objects":objects})),signals={"episode_count":len(episodes),"known_positions":len(visited),"known_objects":len(objects)})


class LifePredictionModule(PsycheModule):
    module_id = "PSY-PREDICTION-LIFE-V01"; version = "0.2.1"; stage = PsycheStage.PREDICTION
    def process(self, context: PsycheContext) -> PsycheOutput:
        attended=context.state.attention.get("current",{}); attended=attended if isinstance(attended,dict) else {}; actions=attended.get("available_actions",()); current=_position(attended.get("position")); models=context.state.learning.get("action_models",{}); spatial=context.state.memory.get("spatial",{}); objects=spatial.get("objects",{}) if isinstance(spatial,dict) else {}
        predictions={}
        for raw in actions:
            action=str(raw); model=models.get(action,{}) if isinstance(models,dict) else {}; mean=model.get("mean",{}) if isinstance(model,dict) else {}; prediction={str(k):float(v) for k,v in mean.items() if isinstance(v,(int,float)) and not isinstance(v,bool)}
            dest=_move_destination(action)
            if dest is not None and current is not None:
                nav=0.0
                for object_id, rec in objects.items() if isinstance(objects,dict) else ():
                    if not isinstance(rec,dict): continue
                    objpos=_position(rec.get("position")); interaction=models.get(f"USE:{object_id}",{}) if isinstance(models,dict) else {}; consequence=interaction.get("mean",{}) if isinstance(interaction,dict) else {}
                    if objpos is None or not isinstance(consequence,dict) or not consequence: continue
                    numeric={str(k):float(v) for k,v in consequence.items() if isinstance(v,(int,float)) and not isinstance(v,bool)}
                    benefit=_homeostatic_gain(numeric,context.state.internal,context.state.goals)+float(context.state.goals.get("progress_weight",0.0))*float(numeric.get("progress_delta",0.0))
                    if benefit <= 0: continue
                    before=_manhattan(current,objpos); after=_manhattan(dest,objpos); improvement=before-after
                    if improvement>0: nav=max(nav,benefit*improvement/max(1.0,float(before)))
                prediction["__navigation_value"]=nav
            predictions[action]=prediction
        return PsycheOutput(updates=(PsycheUpdate("predictions","by_action",predictions),),signals={"by_action":predictions})


class LifePredictionErrorModule(PsycheModule):
    module_id = "PSY-PREDICTION-ERROR-LIFE-V01"; version = "0.2.1"; stage = PsycheStage.PREDICTION_ERROR
    def process(self, context: PsycheContext) -> PsycheOutput:
        attended=context.state.attention.get("current",{}); previous=context.state.predictions.get("last_selected"); errors={}
        if isinstance(attended,dict) and isinstance(previous,dict) and attended.get("last_action")==previous.get("action") and isinstance(attended.get("last_consequence"),dict):
            actual=attended["last_consequence"]; expected=previous.get("prediction",{}); keys={str(k) for k in set(actual)|set(expected) if not str(k).startswith("__") and str(k)!="invalid_action"}
            for k in keys:
                a=actual.get(k,0.0); e=expected.get(k,0.0)
                if isinstance(a,(int,float)) and not isinstance(a,bool) and isinstance(e,(int,float)) and not isinstance(e,bool): errors[k]=float(a)-float(e)
        magnitude=sum(abs(v) for v in errors.values())
        return PsycheOutput(updates=(PsycheUpdate("prediction_errors","last",errors),PsycheUpdate("prediction_errors","magnitude",magnitude)),signals={"errors":errors,"magnitude":magnitude})


class LifeUncertaintyModule(PsycheModule):
    module_id = "PSY-UNCERTAINTY-LIFE-V01"; version = "0.2.1"; stage = PsycheStage.UNCERTAINTY
    def process(self, context: PsycheContext) -> PsycheOutput:
        attended=context.state.attention.get("current",{}); actions=attended.get("available_actions",()) if isinstance(attended,dict) else (); models=context.state.learning.get("action_models",{}); uncertainty={}
        for raw in actions:
            action=str(raw); model=models.get(action,{}) if isinstance(models,dict) else {}; count=int(model.get("count",0) if isinstance(model,dict) else 0); uncertainty[action]=1.0/sqrt(count+1.0)
        return PsycheOutput(updates=(PsycheUpdate("uncertainty","by_action",uncertainty),),signals={"by_action":uncertainty})


class LifeGlobalModulationModule(PsycheModule):
    module_id = "PSY-GLOBAL-MODULATION-LIFE-V01"; version = "0.2.1"; stage = PsycheStage.GLOBAL_MODULATION
    def process(self, context: PsycheContext) -> PsycheOutput:
        tension=float(context.state.global_state.get("tension",0.0)); u=context.state.uncertainty.get("by_action",{}); average=sum(float(v) for v in u.values())/len(u) if isinstance(u,dict) and u else 0.0; gain=max(0.0,min(0.55,0.06+0.34*average-0.28*tension))
        return PsycheOutput(updates=(PsycheUpdate("global_state","exploration_gain",gain),),signals={"tension":tension,"average_uncertainty":average,"exploration_gain":gain})


class LifeValuationModule(PsycheModule):
    module_id = "PSY-VALUATION-LIFE-V01"; version = "0.2.1"; stage = PsycheStage.VALUATION
    def process(self, context: PsycheContext) -> PsycheOutput:
        predictions=context.state.predictions.get("by_action",{}); habits=context.state.habits.get("strength",{}); goals=context.state.goals; pw=float(goals.get("progress_weight",0.42)); hw=float(goals.get("habit_weight",0.035)); nw=float(goals.get("navigation_weight",0.90)); values={}
        if isinstance(predictions,dict):
            for action, raw in predictions.items():
                pred=raw if isinstance(raw,dict) else {}; numeric={str(k):float(v) for k,v in pred.items() if isinstance(v,(int,float)) and not isinstance(v,bool) and not str(k).startswith("__")}; home=_homeostatic_gain(numeric,context.state.internal,goals); progress=float(numeric.get("progress_delta",0.0))*pw; habit=(float(habits.get(action,0.0)) if isinstance(habits,dict) else 0.0)*hw; nav=float(pred.get("__navigation_value",0.0))*nw; values[str(action)]={"homeostasis":home,"progress":progress,"habit":habit,"navigation":nav,"base_total":home+progress+habit+nav}
        return PsycheOutput(updates=(PsycheUpdate("values","by_action",values),),signals={"by_action":values})


class LifeActionGenerationModule(PsycheModule):
    module_id = "PSY-ACTION-GENERATION-LIFE-V01"; version = "0.2.1"; stage = PsycheStage.ACTION_GENERATION
    def process(self, context: PsycheContext) -> PsycheOutput:
        attended=context.state.attention.get("current",{}); actions=attended.get("available_actions",()) if isinstance(attended,dict) else (); values=context.state.values.get("by_action",{}); uncertainty=context.state.uncertainty.get("by_action",{}); candidates=[]
        for raw in actions:
            action=str(raw); rec=values.get(action,{}) if isinstance(values,dict) else {}; comp=dict(rec) if isinstance(rec,dict) else {}; total=float(comp.pop("base_total",0.0)); candidates.append(PsycheActionCandidate(source_module=self.module_id,action=Action(action),total_value=total,components={str(k):float(v) for k,v in comp.items() if isinstance(v,(int,float)) and not isinstance(v,bool)},metadata={"uncertainty":float(uncertainty.get(action,1.0) if isinstance(uncertainty,dict) else 1.0),"local_interaction":action.startswith("USE:"),"movement":action.startswith("MOVE:")}))
        return PsycheOutput(candidates=tuple(candidates),signals={"candidate_count":len(candidates),"actions":[c.action.kind for c in candidates]})


class LifeActionSelectionModule(PsycheModule):
    module_id = "PSY-ACTION-SELECTION-LIFE-V01"; version = "0.2.1"; stage = PsycheStage.ACTION_SELECTION
    def process(self, context: PsycheContext) -> PsycheOutput:
        if not context.candidates:
            return PsycheOutput(selection=PsycheSelection(source_module=self.module_id,action=Action.wait(),reason="NO_CANDIDATES",score=0.0))
        models=context.state.learning.get("action_models",{}); counts={}
        for c in context.candidates:
            rec=models.get(c.action.kind,{}) if isinstance(models,dict) else {}; counts[c.action.kind]=int(rec.get("count",0) if isinstance(rec,dict) else 0)
        novel=[c for c in context.candidates if c.metadata.get("local_interaction") and counts.get(c.action.kind,0)==0]
        if novel:
            selected=sorted(novel,key=lambda c:c.action.kind)[0]; reason="NOVEL_AFFORDANCE_PROBE"; score=selected.total_value
        else:
            gain=float(context.state.global_state.get("exploration_gain",0.0)); tension=float(context.state.global_state.get("tension",0.0))
            def adjusted(c): return c.total_value+gain*float(c.metadata.get("uncertainty",0.0))
            unexplored=[c for c in context.candidates if c.metadata.get("movement") and counts.get(c.action.kind,0)==0]
            best_known=max((adjusted(c) for c in context.candidates if counts.get(c.action.kind,0)>0),default=float("-inf"))
            if unexplored and (tension<0.34 or best_known<=0.0):
                selected=sorted(unexplored,key=lambda c:(-float(c.metadata.get("uncertainty",0.0)),c.action.kind))[0]; reason="SPATIAL_EXPLORATION"; score=adjusted(selected)
            else:
                selected=sorted(context.candidates,key=lambda c:(-adjusted(c),c.action.kind))[0]; reason="MULTI_OBJECTIVE_VALUE_PLUS_UNCERTAINTY"; score=adjusted(selected)
        prediction=context.state.predictions.get("by_action",{}).get(selected.action.kind,{})
        return PsycheOutput(updates=(PsycheUpdate("predictions","last_selected",{"action":selected.action.kind,"prediction":deepcopy(prediction)}),PsycheUpdate("working","last_selection",{"action":selected.action.kind,"reason":reason,"score":score})),selection=PsycheSelection(source_module=self.module_id,action=selected.action,reason=reason,score=score,metadata={"base_value":selected.total_value,"components":deepcopy(selected.components),"uncertainty":selected.metadata.get("uncertainty",0.0)}),signals={"selected_action":selected.action.kind,"reason":reason,"score":score})


def build_life_modules():
    return (
        LifeInternalRegulationModule(), PerceptionModule(), LifeAttentionModule(), LifeOutcomeLearningModule(), LifeSpatialMemoryModule(),
        LifePredictionModule(), LifePredictionErrorModule(), LifeUncertaintyModule(), GoalMaintenanceModule(), LifeGlobalModulationModule(),
        SelfModelModule(), HabitModule(), LifeValuationModule(), LifeActionGenerationModule(), LifeActionSelectionModule(),
    )
