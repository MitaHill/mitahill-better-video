<template>
  <div>
    <div class="wm-timeline">
      <div class="wm-head">
        <span>水印时间轴分段</span>
        <button class="secondary wm-add-btn" type="button" @click="addWatermarkSegment">新增分段</button>
      </div>
      <div class="wm-segment" v-for="(seg, idx) in convertForm.watermarkTimeline" :key="seg.id">
        <div class="inline-grid four">
          <div class="field compact"><label>标签</label><input v-model="seg.label" placeholder="A/B/C" /></div>
          <div class="field compact"><label>类型</label><select v-model="seg.sourceType"><option value="text">文字</option><option value="image">图片</option></select></div>
          <div class="field compact"><label>开始(秒)</label><input v-model.number="seg.startSec" type="number" min="0" step="0.1" /></div>
          <div class="field compact"><label>结束(秒)</label><input v-model.number="seg.endSec" type="number" min="0" step="0.1" /></div>
        </div>
        <div class="inline-grid four">
          <div class="field compact" v-if="seg.sourceType === 'text'"><label>文字内容</label><input v-model="seg.text" placeholder="水印文本" /></div>
          <div class="field compact" v-else><label>图片索引</label><input v-model.number="seg.imageIndex" type="number" min="0" :max="Math.max(0, convertForm.watermarkImages.length - 1)" /></div>
          <div class="field compact"><label>位置</label><select v-model="seg.position"><option value="top_left">左上</option><option value="top_right">右上</option><option value="bottom_left">左下</option><option value="bottom_right">右下</option><option value="center">居中</option><option value="custom">手动</option></select></div>
          <div class="field compact"><label>旋转角度</label><input v-model.number="seg.rotationDeg" type="number" min="-180" max="180" step="1" /></div>
          <div class="field compact"><label>透明度</label><input v-model.number="seg.alpha" type="number" min="0.05" max="1" step="0.05" /></div>
        </div>
        <div class="inline-grid three" v-if="seg.position === 'custom' || seg.animation === 'none'">
          <div class="field compact"><label>X 表达式</label><input v-model="seg.xExpr" placeholder="例如: W-w-24" /></div>
          <div class="field compact"><label>Y 表达式</label><input v-model="seg.yExpr" placeholder="例如: H-h-24" /></div>
          <div class="field compact"><label>动画</label><select v-model="seg.animation"><option value="none">静态</option><option value="swing">不断摆动</option><option value="dvd_bounce">DVD 图标撞墙</option></select></div>
        </div>
        <div class="wm-actions">
          <label class="check-inline"><input type="checkbox" v-model="seg.enabled" />启用该分段</label>
          <button class="secondary" type="button" @click="removeWatermarkSegment(idx)">删除分段</button>
        </div>
      </div>
    </div>

    <div class="field">
      <label>高级 Lua 自定义</label>
      <div class="inline-grid two">
        <label class="check-inline"><input type="radio" name="watermark-lua-enable" :value="false" v-model="convertForm.watermarkLuaEnabled" />关闭</label>
        <label class="check-inline"><input type="radio" name="watermark-lua-enable" :value="true" v-model="convertForm.watermarkLuaEnabled" />启用</label>
      </div>
    </div>
    <div class="field" v-if="convertForm.watermarkLuaEnabled">
      <label>Lua Table 风格脚本（填写后将覆盖上方分段配置）</label>
      <textarea v-model="convertForm.watermarkLuaScript" rows="6" placeholder="return { {label='A', source_type='text', text='WM', start_sec=0, end_sec=3, position='bottom_right', rotation_deg=10, animation='swing'} }"></textarea>
      <label>导入脚本文件</label>
      <input type="file" accept=".lua,.txt,text/plain" @change="onWatermarkLuaFileChange" />
    </div>
  </div>
</template>

<script setup>
defineProps({
  convertForm: {
    type: Object,
    required: true,
  },
  addWatermarkSegment: {
    type: Function,
    required: true,
  },
  removeWatermarkSegment: {
    type: Function,
    required: true,
  },
  onWatermarkLuaFileChange: {
    type: Function,
    required: true,
  },
});
</script>
