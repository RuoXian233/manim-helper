import json
import warnings
from typing import Any
from dataclasses import dataclass
# Just allow eval() to access
from math import *

from manim import *
# Just allow eval() to access
import numpy as np
    

class MObjectManager:

    class InvalidObjectException(Exception):
        pass

    @staticmethod
    def _mobject_shift(_: 'MObjectManager', o: Mobject, v: str, t: str) -> None:
        o.shift(eval(v.format(t.split('_')[-1])))

    @staticmethod
    def _mobject_color(_: 'MObjectManager', o: Mobject, v: str, __: str) -> None:
        o.set_color(v)

    @staticmethod
    def _mobject_scale(_: 'MObjectManager', o: Mobject, v: float | int | str, __: str) -> None:
        if isinstance(v, (int, float)):
            o.scale(v)
        else:
            o.scale(eval(v))

    @staticmethod
    def _mobject_move_to(m: 'MObjectManager', o: Mobject, d: str, _: str) -> None:
        o.move_to(m.get_object(d))

    @staticmethod
    def _mobject_associate(m: 'MObjectManager', o: Mobject, f: str, _: str) -> None:
        o.add_updater(eval(f'lambda this: {f}'))

    supported_attributes = {}
    value_optional_types = ('circle', "axes")

    def __init__(self) -> None:
        self._objects: list[str] = []

    def get_object(self, name: str) -> Any:
        if name not in self._objects:
            raise MObjectManager.InvalidObjectException(
                f'Cannot find object "{name}"'
            )
        return getattr(self, name)

    def add_object(self, name: str, value: Any) -> None:
        if name in self._objects:
            raise MObjectManager.InvalidObjectException(
                f'Object `{name}` already exists'
            )
        
        setattr(self, name, value)
        self._objects.append(name)

    def update_attributes(self) -> None:
        for attr in self._objects:
            value = getattr(self, attr)
            if isinstance(value, str):
                setattr(self, attr, Text(value))

            def process_dict(value, apply: bool = True) -> None | Any:
                val = None
                if 'type' not in value:
                    value['type'] = 'text'
                if 'value' not in value and value['type'] not in MObjectManager.value_optional_types:
                    raise MObjectManager.InvalidObjectException(
                        f'Object `{attr}` should has an value'
                    )

                try:
                    real_val: Any | None
                    if 'value' in value:
                        real_val = value['value']
                        if isinstance(value['value'], str):
                            v = value['value']
                            if v.startswith('$'):
                                real_val = getattr(self, v.lstrip('$'))
                            elif v.startswith('%'):
                                allow_access = len(v.split('.')) > 1
                                real_val = eval(f'{"self." if allow_access else ""}{v[1:]}')
                    else:
                        real_val = None

                    properties = {} if 'properties' not in value else value['properties']
                    val: Any
                    updates = {}

                    for k, v in properties.items():
                        if isinstance(v, str) and v.startswith('%'):
                            updates[k] = eval(v[1:])
                    for k, v in updates.items():
                        properties[k] = v

                    allow_access = False
                    if len(value['type'].split('.')) > 1:
                        allow_access = True

                    print(real_val, properties)
                    if real_val is not None:
                        val = eval(f'{"self." if allow_access else ""}{value["type"][0].upper() if not allow_access else value["type"][0]}{value["type"][1:]}')(real_val, **properties)
                    else:
                        val = eval(f'{"self." if allow_access else ""}{value["type"][0].upper() if not allow_access else value["type"][0]}{value["type"][1:]}')(**properties)

                    if apply:
                        if isinstance(val, Mobject):
                            val.__manager__ = self
                            val.find = val.__manager__.get_object
                        setattr(self, attr, val)
                except Exception as e:
                    raise MObjectManager.InvalidObjectException(
                        'Failed to create object'
                    ) from e

                for k, v in value.items():
                    if k in ('type', 'value'):
                        continue
                    elif k not in MObjectManager.supported_attributes and k != 'properties':
                        raise MObjectManager.InvalidObjectException(
                            f'Unsupported attribute: {k}'
                        )
                    else:
                        if apply:
                            if k != 'properties':
                                MObjectManager.supported_attributes[k](self, getattr(self, attr), v, attr)
                        else:
                            return val

            if isinstance(value, dict):
                process_dict(value)
            
            if isinstance(value, list):
                setattr(self, attr, VGroup(*[self.get_object(item) for item in value]))                    


MObjectManager.supported_attributes = { 
    '_'.join(key.split('_')[2:]): getattr(MObjectManager, key) for key in dir(MObjectManager) if key.startswith('_mobject_')   
}


class TextLoader:
    '''
    A simple loader to load text content from a json file

    Syntax:    "[{id}.]{names}[-{qualification}]*
    '''
    class LoadException(Exception):
        pass

    def __init__(self, text_file: str) -> None:
        self._src_file = text_file


    def load(self) -> dict[str, str]:
        raw_content: dict[str, str]
        try:
            with open(self._src_file, 'r', encoding='utf-8') as f:
                raw_content = json.loads(f.read())

        except (OSError, json.JSONDecodeError) as e:
            raise TextLoader.LoadException(
                f'Error while deserializing json object: {e}'
            )
        except Exception as fatal:
            raise TextLoader.LoadException(fatal)

        return raw_content
    
    def apply_to(self, o: object, content: dict[str, Any]) -> None:
        if o is not None:
            for k, v in content.items():
                index_num = ''
                remains = ''
                formatted_name = ''
                if len(index := k.split('.')) not in (1, 2):
                    raise TextLoader.LoadException(
                        f'Invalid syntax: `.` should only be used to mark index'
                    )
                elif len(index) == 1:
                    remains = index[0]
                elif len(index) == 2:
                    index_num, remains = index
                    try:
                        int(index_num)
                    except ValueError as e:
                        raise TextLoader.LoadException(
                            f'Invalid index format: {e}'
                        )

                remains = remains.replace('-', '_')
                formatted_name = remains if not index_num else f'{remains}_{index_num}'
                setattr(o, formatted_name, v)


    def apply(self, content: dict[str, Any]) -> MObjectManager:
        manager = MObjectManager()

        for k, v in content.items():
            index_num = ''
            remains = ''
            formatted_name = ''
            if len(index := k.split('.')) not in (1, 2):
                raise TextLoader.LoadException(
                    f'Invalid syntax: `.` should only be used to mark index'
                )
            elif len(index) == 1:
                remains = index[0]
            elif len(index) == 2:
                index_num, remains = index
                try:
                    int(index_num)
                except ValueError as e:
                    raise TextLoader.LoadException(
                        f'Invalid index format: {e}'
                    )

            remains = remains.replace('-', '_')
            formatted_name = remains if not index_num else f'{remains}_{index_num}'
            manager.add_object(formatted_name, v)

        manager.update_attributes()
        return manager


class Director:

    # execution write support 0 positional argument and 0 property
    basic_property = { 'duration': 'run_time' }
    animation_controller_mapping = [AnimationGroup, Succession, LaggedStart]

    @dataclass
    class AnimationWithPlayArguments:
        animation: Animation
        execution_cfg: dict[str, Any]
        animation_method: str | None
        invoke_params: list[Any]
        related: Mobject | None = None

    executions = {
         'write': (Write, 0, {}),
         'unwrite': (Unwrite, 0, {}),
         'create': (Create, 0, {}),
         'uncreate': (Uncreate, 0, {}),
         'transform': (ReplacementTransform, 1, {}),
         'translate': ('shift', 1, {}),
         'scale': ('scale', 1, {}),
         'shift': ('shift', 1, {}),
         'parallel': (0, 1, {}),
         'succession': (1, -1, {}),
         'lagged': (2, -1, { 'ratio': 'lag_ratio' }),
         'wait': (-1, 1, {}),
         'select': (-2, -1, { 'action': 'action' }),
         'add': (-3, -1, {}),
         'trace': (MoveAlongPath, 1, {})
    }

    @staticmethod
    def _execute_simple(d: 'Director', a: Any, t: str, args: list[Any], kwargs: dict[str, Any], cfg: dict[str, Any]) -> None:
        evaluated = []
        for arg in args:
            if isinstance(arg, str) and arg.startswith('$'):
                evaluated.append(d.om.get_object(arg[1:]))
            else:
                evaluated.append(arg)
        
        d.target.play(
            a(d.om.get_object(t), *evaluated, **kwargs),
            **cfg
        )

    @staticmethod
    def _execute_shift(d: 'Director', t: str, args: list[Any], _: dict[str, Any], cfg: dict[str, Any]) -> None:
        assert len(args) == 1, 'Invalid parameters for action `shift`'
        d.target.play(
            getattr(d.om.get_object(t).animate, 'shift')(eval(args[0])),
            **cfg
        )

    @staticmethod
    def _execute_scale(d: 'Director', t: str, args: list[Any], _: dict[str, Any], cfg: dict[str, Any]) -> None:
        assert len(args) == 1, 'Invalid parameters for action `scale`'
        if isinstance(args[0], str):
            d.target.play(
                getattr(d.om.get_object(t).animate, 'scale')(eval(args[0])),
                **cfg
            )
        else:
            d.target.play(
                getattr(d.om.get_object(t).animate, 'scale')(args[0]),
                **cfg
            )

    @staticmethod
    def _pack_simple(d: 'Director', a: Any, t: str, args: list[Any], kwargs: dict[str, Any], cfg: dict[str, Any]) -> AnimationWithPlayArguments:
        evaluated = []
        for arg in args:
            if isinstance(arg, str) and arg.startswith('$'):
                evaluated.append(d.om.get_object(arg[1:]))
            else:
                evaluated.append(arg)
        
        return Director.AnimationWithPlayArguments(
            a(d.om.get_object(t), *evaluated, **kwargs), cfg, None, []
        )
    
    @staticmethod
    def _pack_shift(d: 'Director', t: str, args: list[Any], kwargs: dict[str, Any], cfg: dict[str, Any]) -> AnimationWithPlayArguments:
        assert len(args) == 1, 'Invalid parameters for action `shift`'
        a = eval(args[0])
        ob = d.om.get_object(t)
        return Director.AnimationWithPlayArguments(
           ob.animate.shift(a), cfg, 'shift', [a], ob
        )
    
    @staticmethod
    def _pack_scale(d: 'Director', t: str, args: list[Any], kwargs: dict[str, Any], cfg: dict[str, Any]) -> AnimationWithPlayArguments:
        assert len(args) == 1, 'Invalid parameters for action `scale`'
        ob = d.om.get_object(t)
        if isinstance(args[0], str):
            a = eval(args[0])
            return Director.AnimationWithPlayArguments(
                ob.animate.scale(a),
                cfg, 'scale', [a], ob
            )
        else:
            return Director.AnimationWithPlayArguments(
                ob.animate.scale(args[0]),
                cfg, 'scale', [args[0]], ob
            )
        
    class ExecutionException(Exception):
        pass
    
    def __init__(self, om: MObjectManager, action_script: str) -> None:
        self.om = om
        self._action_script_src = action_script
        self.target = None
        self.actions = []

    def set_target_show(self, show: Scene) -> None:
        self.target = show

    def load_actions(self) -> None:
        try:
            actions: dict[str, Any]
            with open(self._action_script_src, 'r', encoding='utf-8') as f:
                actions = json.loads(f.read())

            for k, v in actions.items():
                self.actions.append({
                    'scene': k,
                    'procedure': v
                })
        except Exception as e:
            raise Director.ExecutionException('Failed to load actions from file') from e

    def generate_action_sequence(self, seq: list[Any]) -> list[AnimationWithPlayArguments]:
        result = []

        for action in seq:
            if 'action' not in action:
                raise Director.ExecutionException('An action must be specified')
            action_name = action['action']
            if action_name not in Director.executions:
                raise Director.ExecutionException(
                    f'Action `{action_name}` is unsupported'
                )
            
            action_object, action_cargs, action_kwargs = Director.executions[action_name]
            cfg = {}
                    
            if isinstance(action_object, int):
                if 'params' not in action:
                    raise Director.ExecutionException('Missing parameters')

                if action_object == -1:
                    if len(action['params']) != 1 or len(action.keys()) != 2:
                        raise Director.ExecutionException('Invalid parameters for action `wait`')
                    result.append(Director.AnimationWithPlayArguments(Wait(action['params'][0]), {}, None, []))
                elif action_object == -2:
                    if 'target' not in action:
                        raise Director.ExecutionException('Missing general target for selection')
                    elif 'params' not in action:
                        raise Director.ExecutionException('Missing replacement parameters for selection')
                    elif 'properties' not in action:
                        raise Director.ExecutionException('Missing actions for selection')
                    else:
                        if not isinstance(action['params'], list):
                                action['params'] = eval(action['params'])

                        for param in action['params']:
                            action_details = action['properties']
                            action_details['target'] = action['target'].format(param)
                            for sub_actions in self.generate_action_sequence([action_details]):
                                result.append(sub_actions)
                elif action_object == -3:
                    raise Director.ExecutionException(
                        "Action `add` should not be placed inside an animation controller"
                    )
                else:
                    for k, v in action.items():
                        if k in ('action', 'target', 'params', 'async', 'properties'):
                            continue
                        elif k in Director.basic_property.keys():
                            cfg[Director.basic_property[k]] = v
                        else:
                            raise Director.ExecutionException(
                                f'Config `{k}` is invalid'
                            )

                    # if 'target' in action:
                    #     raise Director.ExecutionException('Animation controller use params as target')
                    if 'params' not in action:
                        raise Director.ExecutionException('Animation controller needs an animated sequence as paramater')
                    animation_controller = Director.animation_controller_mapping[action_object]

                    result.append(Director.AnimationWithPlayArguments(animation_controller(
                        *[a.animation for a in self.generate_action_sequence(action['params'])],
                        **({} if 'properties' not in action else action['properties'])
                    ), cfg, None, []))

            elif isinstance(action_object, str):
                for k, v in action.items():
                    if k in ('action', 'target', 'params', 'properties'):
                        continue
                    if k in Director.basic_property:
                        cfg[Director.basic_property[k]] = v
                    else:
                        raise Director.ExecutionException(
                            f'Config `{k}` is invalid'
                        )

                if 'params' not in action:
                    raise Director.ExecutionException('Missing parameters')
                if 'target' not in action:
                        raise Director.ExecutionException('An action target must be specified')
                
                result.append(getattr(self.__class__, f'_pack_{action_object}')(
                    self, 
                    action['target'],
                    action['params'],
                    {} if 'properties' not in action else action['properties'],
                    cfg
                ))
            else:
                for k, v in action.items():
                    if k in ('action', 'target', 'params', 'properties'):
                        continue
                    if k in Director.basic_property:
                        cfg[Director.basic_property[k]] = v
                    else:
                        raise Director.ExecutionException(
                            f'Config `{k}` is invalid'
                        )

                if 'target' not in action:
                        raise Director.ExecutionException('An action target must be specified')
                
                if action_cargs:
                    if 'params' not in action or (len(action['params']) != action_cargs and action_cargs != -1) or (len(action['params']) < 1 and action_cargs == -1):
                        warnings.warn(f'Unsufficient positional arguments for action `{action_name}`')

                if 'properties' not in action and len(action_kwargs):
                    warnings.warn(f'Missing properties for `{action_name}`')
                
                elif len(action_kwargs):
                    for a in action_kwargs:
                        if a not in action['properties'].keys():
                            warnings.warn(f'Missing property \'{a}\' for `{action_name}`')

                result.append(Director._pack_simple(
                    self,
                    action_object,
                    action['target'],
                    [] if 'params' not in action else action['params'],
                    {} if 'properties' not in action else action['properties'],
                    cfg
                ))  
        return result

    def start_play(self) -> None:
        if self.target is None:
            raise Director.ExecutionException(
                f'Show has not been set'
            )
        
        for scene in self.actions:
            for action in scene['procedure']:
                if 'action' not in action:
                    raise Director.ExecutionException('An action must be specified')
                action_name = action['action']
                if action_name not in Director.executions:
                    raise Director.ExecutionException(
                        f'Action `{action_name}` is unsupported'
                    )
                
                action_object, action_cargs, action_kwargs = Director.executions[action_name]
                cfg = {}
                        
                if isinstance(action_object, int):
                    if 'params' not in action and action_object != -3:
                        raise Director.ExecutionException('Missing parameters')

                    if action_object == -1:
                        if len(action['params']) != 1 or len(action.keys()) != 2:
                            raise Director.ExecutionException('Invalid parameters for action `wait`')
                        self.target.wait(action['params'][0])
                    elif action_object == -2:
                        cache = []
                        if 'target' not in action:
                            raise Director.ExecutionException('Missing general target for selection')
                        elif 'params' not in action:
                            raise Director.ExecutionException('Missing replacement parameters for selection')
                        elif 'properties' not in action:
                            raise Director.ExecutionException('Missing actions for selection')
                        else:
                            if not isinstance(action['params'], list):
                                action['params'] = eval(action['params'])

                            for param in action['params']:
                                action_details = action['properties']
                                action_details['target'] = action['target'].format(param)
                                for sub_actions in self.generate_action_sequence([action_details]):
                                    cache.append(sub_actions)
                        for c in cache:
                            self.target.play(c, **c.execution_cfg)
                    elif action_object == -3:
                        if 'target' not in action:
                            raise Director.ExecutionException('Missing target to add')
                        self.target.add(self.om.get_object(action['target']))

                    else:
                        for k, v in action.items():
                            if k in ('action', 'target', 'params', 'properties', 'async'):
                                continue
                            elif k in Director.basic_property.keys():
                                cfg[Director.basic_property[k]] = v
                            else:
                                raise Director.ExecutionException(
                                    f'Config `{k}` is invalid'
                                )

                        if 'target' in action:
                            raise Director.ExecutionException('Animation controller use parameters as target')
                        if 'params' not in action:
                            raise Director.ExecutionException('Animation controller needs an animated sequence as paramater')
                        animation_controller = Director.animation_controller_mapping[action_object]

                        controller_params = {} if 'properties' not in action else {
                            action_kwargs[k]: v for k, v in action['properties'].items()
                        }

                        timeline = [ao for ao in self.generate_action_sequence(action['params'])]
                        nodes = [ao.animation for ao in timeline]

                        if 'async' in action and action['async']:
                            nodes = []
                            def _method(m):
                                for node in timeline:
                                    getattr(m, node.animation_method)(*node.invoke_params)
                                return m
                            
                            for i in timeline:
                                nodes.append(ApplyFunction(_method, i.related))

                        print(nodes)
                        self.target.play(animation_controller(
                            *nodes,
                            **controller_params
                        ), **cfg)

                elif isinstance(action_object, str):
                    for k, v in action.items():
                        if k in ('action', 'target', 'params', 'properties'):
                            continue
                        if k in Director.basic_property:
                            cfg[Director.basic_property[k]] = v
                        else:
                            raise Director.ExecutionException(
                                f'Config `{k}` is invalid'
                            )

                    if 'params' not in action:
                        raise Director.ExecutionException('Missing parameters')
                    if 'target' not in action:
                            raise Director.ExecutionException('An action target must be specified')
                    
                    getattr(self.__class__, f'_execute_{action_object}')(
                        self, 
                        action['target'],
                        action['params'],
                        {} if 'properties' not in action else action['properties'],
                        cfg
                    )
                else:
                    for k, v in action.items():
                        if k in ('action', 'target', 'params', 'properties'):
                            continue
                        if k in Director.basic_property:
                            cfg[Director.basic_property[k]] = v
                        else:
                            raise Director.ExecutionException(
                                f'Config `{k}` is invalid'
                            )

                    if 'target' not in action:
                            raise Director.ExecutionException('An action target must be specified')
                    
                    if action_cargs:
                        if 'params' not in action or len(action['params']) != action_cargs:
                            warnings.warn(f'Unsufficient positional arguments for action `{action_name}`')

                    if 'properties' not in action and len(action_kwargs):
                        warnings.warn(f'Missing properties for `{action_name}`')
                    
                    elif len(action_kwargs):
                        for a in action_kwargs:
                            if a not in action['properties'].keys():
                                warnings.warn(f'Missing property \'{a}\' for `{action_name}`')

                    Director._execute_simple(
                        self,
                        action_object,
                        action['target'],
                        [] if 'params' not in action else action['params'],
                        {} if 'properties' not in action else action['properties'],
                        cfg
                    )
