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
        <div class="inline-grid two" v-if="seg.position === 'custom'">
          <div class="field compact"><label>X 表达式</label><input v-model="seg.xExpr" placeholder="例如: W-w-24" /></div>
          <div class="field compact"><label>Y 表达式</label><input v-model="seg.yExpr" placeholder="例如: H-h-24" /></div>
        </div>
        <div class="wm-actions">
          <label class="check-inline"><input type="checkbox" v-model="seg.enabled" />启用该分段</label>
          <button class="secondary" type="button" @click="removeWatermarkSegment(idx)">删除分段</button>
        </div>
      </div>
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
  getFieldPolicy: {
    type: Function,
    required: false,
    default: null,
  },
});
</script>
