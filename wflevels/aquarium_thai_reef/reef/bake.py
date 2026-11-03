"""Bake static reef lighting into opt-in per-corner vertex colors."""
import bpy


def bake_static(objects, material, style):
    """Bake Cycles diffuse illumination and AO; leave other actors dynamic."""
    scene = bpy.context.scene
    old_engine, old_world = scene.render.engine, scene.world
    old_samples = scene.cycles.samples
    world = bpy.data.worlds.new('ReefBakeWorld')
    world.use_nodes = True
    background = world.node_tree.nodes.get('Background')
    background.inputs['Color'].default_value = (.62, .78, 1.0, 1.0)
    background.inputs['Strength'].default_value = .5
    scene.world = world
    light_data = bpy.data.lights.new('ReefBakeSun', 'SUN')
    light_data.energy = 2.0
    light = bpy.data.objects.new('ReefBakeSun', light_data)
    scene.collection.objects.link(light)
    light.rotation_euler = (.32, -.38, -.25)
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 16
    scene.cycles.seed = 20261102
    scene.cycles.use_animated_seed = False
    scene.cycles.use_denoising = False
    scene.render.bake.target = 'VERTEX_COLORS'
    scene.render.bake.use_pass_direct = True
    scene.render.bake.use_pass_indirect = True
    scene.render.bake.use_pass_color = False
    baked_mat = material.copy()
    baked_mat.name = 'reef-atlas-baked'
    baked_mat['wf_prelit'] = True
    baked_mat['wf_baked_vertex_color'] = True
    static_names = {obj.name for obj in objects} | {
        obj.name for obj in scene.objects if obj.name.startswith('reef_')
    }
    hidden = [(obj, obj.hide_render) for obj in scene.objects
              if obj.type == 'MESH' and obj.name not in static_names]
    for obj, _ in hidden:
        obj.hide_render = True
    try:
        for obj in objects:
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            mesh = obj.data
            probe = mesh.color_attributes.new(name='ReefBakeFloat', type='FLOAT_COLOR', domain='CORNER')
            mesh.color_attributes.active_color = probe
            bpy.ops.object.bake(type='AO')
            probe = mesh.color_attributes['ReefBakeFloat']
            ao = [max(0.0, min(1.0, sum(item.color[:3]) / 3.0)) for item in probe.data]
            bpy.ops.object.bake(type='DIFFUSE')
            probe = mesh.color_attributes['ReefBakeFloat']
            lighting = [max(0.0, min(1.0, sum(item.color[:3]) / 3.0)) for item in probe.data]
            mesh.color_attributes.remove(probe)
            result = mesh.color_attributes.new(name='ReefBake', type='BYTE_COLOR', domain='CORNER')
            for index, illumination in enumerate(lighting):
                value = (.25 + .75 * illumination) * (.4 + .6 * ao[index])
                if style == 'anime':
                    value = .35 if value < .48 else .65 if value < .78 else 1.0
                result.data[index].color = (value, value, value, 1.0)
            obj['wf_baked_vertex_color'] = 'ReefBake'
            mesh.materials.clear()
            mesh.materials.append(baked_mat)
            print(f'Reef bake: {obj.name}, {len(result.data)} corners; '
                  f'AO {min(ao):.3f}–{max(ao):.3f}, light {min(lighting):.3f}–{max(lighting):.3f}')
    finally:
        for obj, was_hidden in hidden:
            obj.hide_render = was_hidden
        bpy.data.objects.remove(light, do_unlink=True)
        bpy.data.lights.remove(light_data)
        scene.world = old_world
        bpy.data.worlds.remove(world)
        scene.render.engine = old_engine
        scene.cycles.samples = old_samples
