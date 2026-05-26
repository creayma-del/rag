<template>
  <div class="pipeline-page">
    <!-- 页面标题 -->
    <div class="page-header">
      <h2>RAG 管道可视化</h2>
      <p class="page-desc">
        理解 RAG（检索增强生成）的完整数据流：从文档加载到答案生成，每一步都在做什么、数据如何变化
      </p>
    </div>

    <!-- 离线索引阶段 -->
    <div class="section-divider">
      <span class="divider-text">离线索引阶段 (Ingestion)</span>
      <span class="divider-hint">把文档变成可搜索的向量知识库</span>
    </div>

    <!-- 垂直步骤条 -->
    <div class="stepper">
      <div
        v-for="(step, idx) in ingestionSteps"
        :key="step.step_info.name"
        class="stepper-item"
      >
        <!-- 左侧：连接线 + 圆形编号 -->
        <div class="stepper-rail">
          <div
            class="stepper-node"
            :class="{
              'node-active': expandedSteps.has(step.step_info.name),
              'node-completed': hasSample(step),
            }"
          >
            <span class="node-number">{{ step.step_info.order }}</span>
          </div>
          <div
            v-if="idx < ingestionSteps.length - 1"
            class="stepper-line"
            :class="{ 'line-active': expandedSteps.has(step.step_info.name) }"
          >
            <svg
              class="line-arrow"
              viewBox="0 0 16 24"
              width="16"
              height="24"
            >
              <path
                d="M8 0 L8 18 L3 13 M8 18 L13 13"
                stroke="currentColor"
                stroke-width="1.5"
                fill="none"
              />
            </svg>
          </div>
        </div>

        <!-- 右侧：步骤卡片 -->
        <div
          class="stepper-card"
          :class="{ 'card-expanded': expandedSteps.has(step.step_info.name) }"
        >
          <!-- 卡片头部（点击展开/折叠） -->
          <div
            class="card-header"
            @click="toggleStep(step.step_info.name)"
          >
            <div class="card-title-row">
              <h3 class="card-title">
                {{ step.step_info.label }}
              </h3>
              <el-tag
                v-if="hasSample(step)"
                type="success"
                size="small"
                class="sample-badge"
              >
                有数据
              </el-tag>
              <el-tag
                v-else
                type="info"
                size="small"
                class="sample-badge"
              >
                暂无数据
              </el-tag>
            </div>
            <p class="card-plain-desc">
              {{ plainDescMap[step.step_info.name] }}
            </p>
            <div class="card-meta">
              <span class="meta-item">
                <span class="meta-label">输入</span>
                {{ step.step_info.input_desc }}
              </span>
              <span class="meta-arrow">&#10132;</span>
              <span class="meta-item">
                <span class="meta-label">输出</span>
                {{ step.step_info.output_desc }}
              </span>
            </div>
            <span
              class="expand-icon"
              :class="{ 'icon-expanded': expandedSteps.has(step.step_info.name) }"
            >
              <svg
                viewBox="0 0 24 24"
                width="18"
                height="18"
              >
                <path
                  d="M6 9 L12 15 L18 9"
                  stroke="currentColor"
                  stroke-width="2"
                  fill="none"
                />
              </svg>
            </span>
          </div>

          <!-- 卡片展开内容 -->
          <transition name="card-expand">
            <div
              v-if="expandedSteps.has(step.step_info.name)"
              class="card-body"
            >
              <!-- 步骤描述 -->
              <p class="step-description">
                {{ step.step_info.description }}
              </p>

              <!-- Step 1: 文档加载 -->
              <template v-if="step.step_info.name === 'document_loading'">
                <div
                  v-if="step.sample"
                  class="sample-section"
                >
                  <h4 class="sample-title">
                    文件列表
                  </h4>
                  <div class="file-list">
                    <div
                      v-for="file in (step.sample as DocumentLoadingSample).files"
                      :key="file.name"
                      class="file-card"
                    >
                      <div class="file-icon">
                        <svg
                          viewBox="0 0 24 24"
                          width="20"
                          height="20"
                        >
                          <path
                            d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"
                            stroke="currentColor"
                            stroke-width="1.5"
                            fill="none"
                          />
                          <polyline
                            points="14 2 14 8 20 8"
                            stroke="currentColor"
                            stroke-width="1.5"
                            fill="none"
                          />
                        </svg>
                      </div>
                      <div class="file-info">
                        <span class="file-name">{{ file.name }}</span>
                        <div class="file-tags">
                          <el-tag
                            size="small"
                            type="primary"
                          >
                            {{ file.type_label }}
                          </el-tag>
                          <el-tag
                            size="small"
                            type="info"
                          >
                            {{ formatFileSize(file.size) }}
                          </el-tag>
                        </div>
                      </div>
                    </div>
                  </div>
                  <h4 class="sample-title">
                    解析结果
                    <el-tooltip
                      content="文档被解析成纯文本后的内容预览"
                      placement="top"
                    >
                      <span class="title-hint">?</span>
                    </el-tooltip>
                  </h4>
                  <div
                    v-if="(step.sample as DocumentLoadingSample).text_preview"
                    class="text-preview-block"
                  >
                    <pre class="text-preview-content">{{ (step.sample as DocumentLoadingSample).text_preview }}</pre>
                  </div>
                  <div
                    v-else
                    class="empty-sample-inline"
                  >
                    <p>文档解析预览暂不可用</p>
                  </div>
                  <!-- Loader 映射表 -->
                  <div
                    v-if="Object.keys((step.sample as DocumentLoadingSample).loader_mapping ?? {}).length"
                  >
                    <h4 class="sample-title">
                      Loader 映射表
                      <el-tooltip
                        content="不同文件格式使用不同的 Loader 进行解析"
                        placement="top"
                      >
                        <span class="title-hint">?</span>
                      </el-tooltip>
                    </h4>
                    <div class="reranking-details">
                      <div
                        v-for="(loader, ext) in (step.sample as DocumentLoadingSample).loader_mapping"
                        :key="ext"
                        class="reranking-detail-item"
                      >
                        <el-tag
                          size="small"
                          type="primary"
                        >
                          .{{ ext }}
                        </el-tag>
                        <span class="detail-value mono">{{ loader }}</span>
                      </div>
                    </div>
                  </div>
                  <!-- 编码流程 -->
                  <div
                    v-if="(step.sample as DocumentLoadingSample).process_steps?.length"
                    class="process-flow"
                  >
                    <span class="process-label">编码流程</span>
                    <div class="process-steps">
                      <div
                        v-for="(ps, psi) in (step.sample as DocumentLoadingSample).process_steps"
                        :key="psi"
                        class="process-step-item"
                      >
                        <span class="process-step-text">{{ ps }}</span>
                        <svg
                          v-if="psi < (step.sample as DocumentLoadingSample).process_steps!.length - 1"
                          viewBox="0 0 24 24"
                          width="14"
                          height="14"
                          class="process-arrow"
                        >
                          <path
                            d="M12 4v16m0 0l-6-6m6 6l6-6"
                            stroke="currentColor"
                            stroke-width="2"
                            fill="none"
                          />
                        </svg>
                      </div>
                    </div>
                  </div>
                  <!-- 知识提示 -->
                  <div
                    v-if="(step.sample as DocumentLoadingSample).why_metadata"
                    class="knowledge-tip"
                  >
                    <span class="tip-icon">💡</span>
                    <span class="tip-text">{{ (step.sample as DocumentLoadingSample).why_metadata }}</span>
                  </div>
                </div>
                <div
                  v-else
                  class="empty-sample"
                >
                  <p>还没有上传文档</p>
                  <p class="empty-hint">
                    请先上传文档并构建知识库，这里会展示解析后的文件和文本内容
                  </p>
                </div>
              </template>

              <!-- Step 2: 文本分块 -->
              <template v-if="step.step_info.name === 'text_splitting'">
                <div
                  v-if="step.sample"
                  class="sample-section"
                >
                  <div class="chunk-source">
                    <span class="chunk-source-label">来源文档：</span>
                    <el-tag
                      size="small"
                      type="info"
                    >
                      {{ (step.sample as TextSplittingSample).source }}
                    </el-tag>
                  </div>
                  <!-- 分块配置 -->
                  <div
                    v-if="(step.sample as TextSplittingSample).chunk_strategy"
                    class="retrieval-config"
                  >
                    <el-tag
                      size="small"
                      type="primary"
                    >
                      {{ formatChunkStrategy((step.sample as TextSplittingSample).chunk_strategy!) }}
                    </el-tag>
                    <el-tag
                      v-if="(step.sample as TextSplittingSample).chunk_size"
                      size="small"
                      type="info"
                    >
                      Size: {{ (step.sample as TextSplittingSample).chunk_size }}
                    </el-tag>
                    <el-tag
                      v-if="(step.sample as TextSplittingSample).chunk_overlap"
                      size="small"
                      type="warning"
                    >
                      Overlap: {{ (step.sample as TextSplittingSample).chunk_overlap }}
                    </el-tag>
                  </div>
                  <!-- 策略说明 -->
                  <div
                    v-if="(step.sample as TextSplittingSample).chunk_strategy && (step.sample as TextSplittingSample).strategy_explanation"
                    class="knowledge-tip"
                  >
                    <span class="tip-icon">💡</span>
                    <span class="tip-text">{{ (step.sample as TextSplittingSample).strategy_explanation![(step.sample as TextSplittingSample).chunk_strategy!] }}</span>
                  </div>
                  <!-- 长度分布图 -->
                  <div
                    v-if="Object.keys((step.sample as TextSplittingSample).length_distribution ?? {}).length"
                    class="similarity-distribution"
                  >
                    <span class="sim-label">长度分布</span>
                    <div class="sim-bars">
                      <div
                        v-for="(count, label) in (step.sample as TextSplittingSample).length_distribution"
                        :key="label"
                        class="sim-bar-item"
                      >
                        <span class="sim-bar-rank">{{ label }}</span>
                        <div class="sim-bar-track">
                          <div
                            class="sim-bar-fill"
                            :style="{ width: (count / Math.max(1, Math.max(...Object.values((step.sample as TextSplittingSample).length_distribution!))) * 100) + '%' }"
                          />
                        </div>
                        <span class="sim-bar-value">{{ count }}</span>
                      </div>
                    </div>
                  </div>
                  <!-- 长度统计 -->
                  <div
                    v-if="(step.sample as TextSplittingSample).length_stats"
                    class="embedding-stats"
                  >
                    <div class="stat-item">
                      <span class="stat-label">最小长度</span>
                      <span class="stat-value">{{ (step.sample as TextSplittingSample).length_stats!.min }}</span>
                    </div>
                    <div class="stat-item">
                      <span class="stat-label">最大长度</span>
                      <span class="stat-value">{{ (step.sample as TextSplittingSample).length_stats!.max }}</span>
                    </div>
                    <div class="stat-item">
                      <span class="stat-label">平均长度</span>
                      <span class="stat-value">{{ (step.sample as TextSplittingSample).length_stats!.avg }}</span>
                    </div>
                    <div class="stat-item">
                      <span class="stat-label">总字符数</span>
                      <span class="stat-value">{{ (step.sample as TextSplittingSample).length_stats!.total }}</span>
                    </div>
                  </div>
                  <!-- 编码流程 -->
                  <div
                    v-if="(step.sample as TextSplittingSample).process_steps?.length"
                    class="process-flow"
                  >
                    <span class="process-label">编码流程</span>
                    <div class="process-steps">
                      <div
                        v-for="(ps, psi) in (step.sample as TextSplittingSample).process_steps"
                        :key="psi"
                        class="process-step-item"
                      >
                        <span class="process-step-text">{{ ps }}</span>
                        <svg
                          v-if="psi < (step.sample as TextSplittingSample).process_steps!.length - 1"
                          viewBox="0 0 24 24"
                          width="14"
                          height="14"
                          class="process-arrow"
                        >
                          <path
                            d="M12 4v16m0 0l-6-6m6 6l6-6"
                            stroke="currentColor"
                            stroke-width="2"
                            fill="none"
                          />
                        </svg>
                      </div>
                    </div>
                  </div>
                  <!-- 知识提示 -->
                  <div
                    v-if="(step.sample as TextSplittingSample).why_overlap"
                    class="knowledge-tip"
                  >
                    <span class="tip-icon">💡</span>
                    <span class="tip-text">{{ (step.sample as TextSplittingSample).why_overlap }}</span>
                  </div>
                  <h4 class="sample-title">
                    分块结果
                    <el-tooltip
                      content="长文本被切分成多个小段落，每段就是一个 Chunk，方便后续检索"
                      placement="top"
                    >
                      <span class="title-hint">?</span>
                    </el-tooltip>
                  </h4>
                  <div class="chunk-list">
                    <div
                      v-for="(chunk, chunkIdx) in (step.sample as TextSplittingSample).chunks"
                      :key="chunk.id"
                      class="chunk-card"
                      :class="`chunk-color-${chunkIdx % 4}`"
                    >
                      <div class="chunk-header">
                        <span class="chunk-id">Chunk #{{ chunkIdx + 1 }}</span>
                        <el-tag
                          size="small"
                          :type="chunkIdx % 2 === 0 ? 'primary' : 'success'"
                        >
                          {{ chunk.content_length }} 字
                        </el-tag>
                      </div>
                      <p class="chunk-preview">
                        {{ chunk.content_preview }}
                      </p>
                      <div class="chunk-meta">
                        <el-tag
                          v-for="(val, key) in chunk.metadata"
                          :key="key"
                          size="small"
                          type="info"
                          class="chunk-meta-tag"
                        >
                          {{ key }}: {{ val }}
                        </el-tag>
                      </div>
                    </div>
                  </div>
                </div>
                <div
                  v-else
                  class="empty-sample"
                >
                  <p>还没有分块数据</p>
                  <p class="empty-hint">
                    请先上传文档并构建知识库，这里会展示文本被切分后的结果
                  </p>
                </div>
              </template>

              <!-- Step 3: 向量化 -->
              <template v-if="step.step_info.name === 'embedding'">
                <div
                  v-if="step.sample"
                  class="sample-section"
                >
                  <h4 class="sample-title">
                    文本转向量
                    <el-tooltip
                      content="Embedding 模型把每段文字转换成一组数字（向量），让电脑能理解文本的语义"
                      placement="top"
                    >
                      <span class="title-hint">?</span>
                    </el-tooltip>
                  </h4>
                  <div class="embedding-flow">
                    <!-- 左侧：原始文本 -->
                    <div class="embedding-input">
                      <div class="embedding-label">
                        原始文本 (Chunk)
                      </div>
                      <div class="embedding-text-box">
                        <div class="embedding-chunk-id">
                          ID: {{ (step.sample as EmbeddingSample).chunk_id }}
                        </div>
                        <div
                          v-if="(step.sample as EmbeddingSample).chunk_text"
                          class="embedding-chunk-text"
                        >
                          {{ (step.sample as EmbeddingSample).chunk_text }}<span
                            v-if="((step.sample as EmbeddingSample).chunk_text?.length ?? 0) >= 300"
                            class="text-ellipsis"
                          >...</span>
                        </div>
                      </div>
                    </div>
                    <!-- 中间：转换箭头 -->
                    <div class="embedding-transform">
                      <div class="transform-arrow">
                        <div class="arrow-line" />
                        <svg
                          class="arrow-head"
                          viewBox="0 0 24 24"
                          width="20"
                          height="20"
                        >
                          <path
                            d="M5 12 L19 12 M13 6 L19 12 L13 18"
                            stroke="currentColor"
                            stroke-width="2"
                            fill="none"
                          />
                        </svg>
                      </div>
                      <div class="transform-model">
                        <el-tag
                          size="small"
                          type="warning"
                        >
                          {{ (step.sample as EmbeddingSample).model_name }}
                        </el-tag>
                      </div>
                    </div>
                    <!-- 右侧：向量结果 -->
                    <div class="embedding-output">
                      <div class="embedding-label">
                        向量 (Embedding)
                      </div>
                      <div class="embedding-vector-box">
                        <span class="vector-bracket">[</span>
                        <span
                          v-for="(val, vIdx) in (step.sample as EmbeddingSample).embedding_preview"
                          :key="vIdx"
                          class="vector-value"
                          :class="val >= 0 ? 'vec-positive' : 'vec-negative'"
                        >{{ val >= 0 ? '+' : '' }}{{ val.toFixed(4) }}<span
                          v-if="vIdx < ((step.sample as EmbeddingSample).embedding_preview.length - 1)"
                          class="vector-comma"
                        >,</span></span>
                        <span class="vector-bracket">]</span>
                        <span class="vector-ellipsis"> ... 共 {{ (step.sample as EmbeddingSample).embedding_dimension }} 维</span>
                      </div>
                      <!-- 向量统计 -->
                      <div
                        v-if="(step.sample as EmbeddingSample).embedding_stats"
                        class="embedding-stats"
                      >
                        <div class="stat-item">
                          <span class="stat-label">最小值</span>
                          <span class="stat-value">{{ (step.sample as EmbeddingSample).embedding_stats?.min }}</span>
                        </div>
                        <div class="stat-item">
                          <span class="stat-label">最大值</span>
                          <span class="stat-value">{{ (step.sample as EmbeddingSample).embedding_stats?.max }}</span>
                        </div>
                        <div class="stat-item">
                          <span class="stat-label">均值</span>
                          <span class="stat-value">{{ (step.sample as EmbeddingSample).embedding_stats?.mean }}</span>
                        </div>
                        <div class="stat-item">
                          <span class="stat-label">L2 范数</span>
                          <span class="stat-value">{{ (step.sample as EmbeddingSample).embedding_stats?.norm }}</span>
                        </div>
                      </div>
                      <!-- 向量可视化条 -->
                      <div
                        v-if="(step.sample as EmbeddingSample).embedding_stats"
                        class="embedding-visual"
                      >
                        <span class="visual-label">前 {{ (step.sample as EmbeddingSample).embedding_preview.length }} 维可视化</span>
                        <div class="visual-bars">
                          <div
                            v-for="(val, vIdx) in (step.sample as EmbeddingSample).embedding_preview"
                            :key="vIdx"
                            class="visual-bar-item"
                          >
                            <div
                              class="visual-bar"
                              :style="{
                                height: getBarHeight(val, (step.sample as EmbeddingSample).embedding_stats!) + 'px',
                                background: val >= 0 ? 'rgba(103, 194, 58, 0.6)' : 'rgba(245, 108, 108, 0.6)',
                              }"
                            />
                            <span class="visual-bar-label">{{ vIdx }}</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                  <!-- 编码流程 -->
                  <div
                    v-if="(step.sample as EmbeddingSample).process_steps?.length"
                    class="process-flow"
                  >
                    <span class="process-label">编码流程</span>
                    <div class="process-steps">
                      <div
                        v-for="(ps, psi) in (step.sample as EmbeddingSample).process_steps"
                        :key="psi"
                        class="process-step-item"
                      >
                        <span class="process-step-text">{{ ps }}</span>
                        <svg
                          v-if="psi < (step.sample as EmbeddingSample).process_steps!.length - 1"
                          viewBox="0 0 24 24"
                          width="14"
                          height="14"
                          class="process-arrow"
                        >
                          <path
                            d="M12 4v16m0 0l-6-6m6 6l6-6"
                            stroke="currentColor"
                            stroke-width="2"
                            fill="none"
                          />
                        </svg>
                      </div>
                    </div>
                  </div>
                  <!-- 知识提示 -->
                  <div
                    v-if="(step.sample as EmbeddingSample).why_embedding"
                    class="knowledge-tip"
                  >
                    <span class="tip-icon">💡</span>
                    <span class="tip-text">{{ (step.sample as EmbeddingSample).why_embedding }}</span>
                  </div>
                  <div
                    v-if="(step.sample as EmbeddingSample).what_is_dimension"
                    class="knowledge-tip"
                  >
                    <span class="tip-icon">📐</span>
                    <span class="tip-text">{{ (step.sample as EmbeddingSample).what_is_dimension }}</span>
                  </div>
                </div>
                <div
                  v-else
                  class="empty-sample"
                >
                  <p>还没有向量数据</p>
                  <p class="empty-hint">
                    请先构建知识库，这里会展示文本如何被转换成数字向量
                  </p>
                </div>
              </template>

              <!-- Step 4: 向量存储 -->
              <template v-if="step.step_info.name === 'vector_store'">
                <div
                  v-if="step.sample"
                  class="sample-section"
                >
                  <h4 class="sample-title">
                    向量库状态
                  </h4>
                  <div class="store-status-grid">
                    <div class="store-status-item">
                      <div class="store-status-icon">
                        <svg
                          viewBox="0 0 24 24"
                          width="24"
                          height="24"
                        >
                          <path
                            d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"
                            stroke="currentColor"
                            stroke-width="1.5"
                            fill="none"
                          />
                        </svg>
                      </div>
                      <div class="store-status-content">
                        <span class="store-status-label">向量库</span>
                        <el-tag
                          :type="(step.sample as VectorStoreSample).exists ? 'success' : 'danger'"
                          size="small"
                        >
                          {{ (step.sample as VectorStoreSample).exists ? '已构建' : '未构建' }}
                        </el-tag>
                      </div>
                    </div>
                    <div class="store-status-item">
                      <div class="store-status-icon">
                        <svg
                          viewBox="0 0 24 24"
                          width="24"
                          height="24"
                        >
                          <path
                            d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6"
                            stroke="currentColor"
                            stroke-width="1.5"
                            fill="none"
                          />
                        </svg>
                      </div>
                      <div class="store-status-content">
                        <span class="store-status-label">文档数</span>
                        <span class="store-status-value">{{ (step.sample as VectorStoreSample).documents_count }}</span>
                      </div>
                    </div>
                    <div class="store-status-item">
                      <div class="store-status-icon">
                        <svg
                          viewBox="0 0 24 24"
                          width="24"
                          height="24"
                        >
                          <path
                            d="M4 6h16 M4 12h16 M4 18h16"
                            stroke="currentColor"
                            stroke-width="1.5"
                            fill="none"
                          />
                        </svg>
                      </div>
                      <div class="store-status-content">
                        <span class="store-status-label">总 Chunk 数</span>
                        <span class="store-status-value">{{ (step.sample as VectorStoreSample).total_chunks }}</span>
                      </div>
                    </div>
                    <div class="store-status-item">
                      <div class="store-status-icon">
                        <svg
                          viewBox="0 0 24 24"
                          width="24"
                          height="24"
                        >
                          <circle
                            cx="12"
                            cy="12"
                            r="3"
                            stroke="currentColor"
                            stroke-width="1.5"
                            fill="none"
                          />
                          <path
                            d="M12 1v4 M12 19v4 M4.22 4.22l2.83 2.83 M16.95 16.95l2.83 2.83 M1 12h4 M19 12h4 M4.22 19.78l2.83-2.83 M16.95 7.05l2.83-2.83"
                            stroke="currentColor"
                            stroke-width="1.5"
                            fill="none"
                          />
                        </svg>
                      </div>
                      <div class="store-status-content">
                        <span class="store-status-label">Embedding 模型</span>
                        <span class="store-status-value mono">{{ (step.sample as VectorStoreSample).embedding_model }}</span>
                      </div>
                    </div>
                    <div class="store-status-item">
                      <div class="store-status-icon">
                        <svg
                          viewBox="0 0 24 24"
                          width="24"
                          height="24"
                        >
                          <rect
                            x="3"
                            y="3"
                            width="18"
                            height="18"
                            rx="2"
                            stroke="currentColor"
                            stroke-width="1.5"
                            fill="none"
                          />
                          <path
                            d="M3 9h18 M9 3v18"
                            stroke="currentColor"
                            stroke-width="1.5"
                            fill="none"
                          />
                        </svg>
                      </div>
                      <div class="store-status-content">
                        <span class="store-status-label">向量维度</span>
                        <span class="store-status-value">{{ (step.sample as VectorStoreSample).embedding_dimension }}</span>
                      </div>
                    </div>
                    <div class="store-status-item">
                      <div class="store-status-icon">
                        <svg
                          viewBox="0 0 24 24"
                          width="24"
                          height="24"
                        >
                          <path
                            d="M12 20h9 M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"
                            stroke="currentColor"
                            stroke-width="1.5"
                            fill="none"
                          />
                        </svg>
                      </div>
                      <div class="store-status-content">
                        <span class="store-status-label">分块策略</span>
                        <span class="store-status-value">{{ formatChunkStrategy((step.sample as VectorStoreSample).chunk_strategy) }}</span>
                      </div>
                    </div>
                    <div class="store-status-item">
                      <div class="store-status-icon">
                        <svg
                          viewBox="0 0 24 24"
                          width="24"
                          height="24"
                        >
                          <path
                            d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"
                            stroke="currentColor"
                            stroke-width="1.5"
                            fill="none"
                          />
                        </svg>
                      </div>
                      <div class="store-status-content">
                        <span class="store-status-label">Chunk Size / Overlap</span>
                        <span class="store-status-value">{{ (step.sample as VectorStoreSample).chunk_size }} / {{ (step.sample as VectorStoreSample).chunk_overlap }}</span>
                      </div>
                    </div>
                    <div class="store-status-item">
                      <div class="store-status-icon">
                        <svg
                          viewBox="0 0 24 24"
                          width="24"
                          height="24"
                        >
                          <path
                            d="M12 2L2 7l10 5 10-5-10-5z M2 17l10 5 10-5 M2 12l10 5 10-5"
                            stroke="currentColor"
                            stroke-width="1.5"
                            fill="none"
                          />
                        </svg>
                      </div>
                      <div class="store-status-content">
                        <span class="store-status-label">距离函数</span>
                        <span class="store-status-value mono">{{ (step.sample as VectorStoreSample).distance_function }}</span>
                      </div>
                    </div>
                    <div class="store-status-item">
                      <div class="store-status-icon">
                        <svg
                          viewBox="0 0 24 24"
                          width="24"
                          height="24"
                        >
                          <path
                            d="M3 7v10a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-6l-2-2H5a2 2 0 0 0-2 2z"
                            stroke="currentColor"
                            stroke-width="1.5"
                            fill="none"
                          />
                        </svg>
                      </div>
                      <div class="store-status-content">
                        <span class="store-status-label">存储路径</span>
                        <span class="store-status-value mono">{{ (step.sample as VectorStoreSample).storage_path }}</span>
                      </div>
                    </div>
                  </div>

                  <!-- 索引结构可视化 -->
                  <h4
                    v-if="(step.sample as VectorStoreSample).index_structure?.length"
                    class="sample-title"
                    style="margin-top: 20px;"
                  >
                    索引结构
                    <el-tooltip
                      content="向量库中每个文档被分成了多少个 Chunk，点击可展开查看全部 Chunk ID"
                      placement="top"
                    >
                      <span class="title-hint">?</span>
                    </el-tooltip>
                  </h4>
                  <div
                    v-if="(step.sample as VectorStoreSample).index_structure?.length"
                    class="index-structure"
                  >
                    <div
                      v-for="item in (step.sample as VectorStoreSample).index_structure"
                      :key="item.source"
                      class="index-source-card"
                    >
                      <div
                        class="index-source-header"
                        @click="toggleSource(item.source)"
                      >
                        <span class="index-source-icon">
                          <svg
                            viewBox="0 0 24 24"
                            width="16"
                            height="16"
                          >
                            <path
                              d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6"
                              stroke="currentColor"
                              stroke-width="1.5"
                              fill="none"
                            />
                          </svg>
                        </span>
                        <span class="index-source-name">{{ item.source }}</span>
                        <el-tag
                          size="small"
                          type="primary"
                        >
                          {{ item.chunk_count }} 个 Chunk
                        </el-tag>
                        <span class="index-expand-btn">
                          {{ expandedSources.has(item.source) ? '收起' : '展开全部' }}
                          <svg
                            viewBox="0 0 24 24"
                            width="12"
                            height="12"
                            class="expand-arrow"
                            :class="{ 'arrow-up': expandedSources.has(item.source) }"
                          >
                            <path
                              d="M6 9 L12 15 L18 9"
                              stroke="currentColor"
                              stroke-width="2"
                              fill="none"
                            />
                          </svg>
                        </span>
                      </div>
                      <div class="index-chunk-ids">
                        <template v-if="!expandedSources.has(item.source)">
                          <span
                            v-for="(cid, cidx) in (item.chunk_ids || item.chunk_ids_preview || []).slice(0, 5)"
                            :key="cidx"
                            class="index-chunk-id"
                          >{{ typeof cid === 'string' && cid.length > 8 ? cid.slice(0, 8) + '...' : cid }}</span>
                          <span
                            v-if="(item.chunk_ids || item.chunk_ids_preview || []).length > 5"
                            class="index-chunk-more"
                          >+{{ (item.chunk_ids || item.chunk_ids_preview || []).length - 5 }} 更多（点击展开）</span>
                        </template>
                        <template v-else>
                          <span
                            v-for="(cid, cidx) in (item.chunk_ids || [])"
                            :key="cidx"
                            class="index-chunk-id index-chunk-id-full"
                          >{{ cid }}</span>
                        </template>
                      </div>
                    </div>
                  </div>
                  <!-- 编码流程 -->
                  <div
                    v-if="(step.sample as VectorStoreSample).process_steps?.length"
                    class="process-flow"
                  >
                    <span class="process-label">编码流程</span>
                    <div class="process-steps">
                      <div
                        v-for="(ps, psi) in (step.sample as VectorStoreSample).process_steps"
                        :key="psi"
                        class="process-step-item"
                      >
                        <span class="process-step-text">{{ ps }}</span>
                        <svg
                          v-if="psi < (step.sample as VectorStoreSample).process_steps!.length - 1"
                          viewBox="0 0 24 24"
                          width="14"
                          height="14"
                          class="process-arrow"
                        >
                          <path
                            d="M12 4v16m0 0l-6-6m6 6l6-6"
                            stroke="currentColor"
                            stroke-width="2"
                            fill="none"
                          />
                        </svg>
                      </div>
                    </div>
                  </div>
                  <!-- 知识提示 -->
                  <div
                    v-if="(step.sample as VectorStoreSample).what_is_hnsw"
                    class="knowledge-tip"
                  >
                    <span class="tip-icon">💡</span>
                    <span class="tip-text">{{ (step.sample as VectorStoreSample).what_is_hnsw }}</span>
                  </div>
                  <div
                    v-if="(step.sample as VectorStoreSample).why_cosine"
                    class="knowledge-tip"
                  >
                    <span class="tip-icon">🎯</span>
                    <span class="tip-text">{{ (step.sample as VectorStoreSample).why_cosine }}</span>
                  </div>
                </div>
                <div
                  v-else
                  class="empty-sample"
                >
                  <p>向量库尚未构建</p>
                  <p class="empty-hint">
                    请先上传文档并构建知识库，这里会展示向量库的完整状态信息
                  </p>
                </div>
              </template>

              <!-- 实现模块 -->
              <div class="step-module">
                <span class="module-label">实现模块</span>
                <code class="module-path">{{ step.step_info.module }}</code>
              </div>
            </div>
          </transition>
        </div>
      </div>
    </div>

    <!-- 在线查询阶段 -->
    <div class="section-divider">
      <span class="divider-text">在线查询阶段 (Query)</span>
      <span class="divider-hint">用户提问后，从知识库中检索并生成答案</span>
    </div>

    <div class="ingestion-stages">
      <div
        v-for="(step, idx) in querySteps"
        :key="step.step_info.name"
        class="step-card"
      >
        <div
          class="step-header"
          @click="toggleStep(step.step_info.name)"
        >
          <div class="step-order">
            {{ step.step_info.order }}
          </div>
          <div class="step-title-area">
            <h3 class="step-title">
              {{ step.step_info.label }}
            </h3>
            <p class="step-plain-desc">
              {{ plainDescMap[step.step_info.name] }}
            </p>
          </div>
          <div class="step-meta">
            <el-tag
              v-if="step.sample"
              type="success"
              size="small"
            >
              有数据
            </el-tag>
            <el-tag
              v-else
              type="info"
              size="small"
            >
              无数据
            </el-tag>
            <svg
              viewBox="0 0 24 24"
              width="20"
              height="20"
              class="expand-icon"
              :class="{ 'expanded': expandedSteps.has(step.step_info.name) }"
            >
              <path
                d="M6 9 L12 15 L18 9"
                stroke="currentColor"
                stroke-width="2"
                fill="none"
              />
            </svg>
          </div>
        </div>

        <transition name="step-expand">
          <div
            v-if="expandedSteps.has(step.step_info.name)"
            class="step-body"
          >
            <p class="step-description">
              {{ step.step_info.description }}
            </p>
            <div class="step-io">
              <div class="io-item">
                <span class="io-label">输入</span>
                <span class="io-text">{{ step.step_info.input_desc }}</span>
              </div>
              <div class="arrow-line" />
              <div class="io-item">
                <span class="io-label">输出</span>
                <span class="io-text">{{ step.step_info.output_desc }}</span>
              </div>
            </div>

            <!-- Query Encoder 查询编码 -->
            <template v-if="step.step_info.name === 'query_encoding'">
              <div
                v-if="step.sample"
                class="sample-section"
              >
                <h4 class="sample-title">
                  示例查询编码
                </h4>
                <div class="query-encoding-sample">
                  <!-- 用户问题 -->
                  <div class="query-input-box">
                    <span class="query-label">用户问题</span>
                    <div class="query-text">
                      {{ (step.sample as QueryEncodingSample).sample_question }}
                    </div>
                  </div>
                  <!-- 编码流程 -->
                  <div
                    v-if="(step.sample as QueryEncodingSample).process_steps?.length"
                    class="process-flow"
                  >
                    <span class="process-label">编码流程</span>
                    <div class="process-steps">
                      <div
                        v-for="(ps, psi) in (step.sample as QueryEncodingSample).process_steps"
                        :key="psi"
                        class="process-step-item"
                      >
                        <span class="process-step-text">{{ ps }}</span>
                        <svg
                          v-if="psi < (step.sample as QueryEncodingSample).process_steps.length - 1"
                          viewBox="0 0 24 24"
                          width="14"
                          height="14"
                          class="process-arrow"
                        >
                          <path
                            d="M12 4v16m0 0l-6-6m6 6l6-6"
                            stroke="currentColor"
                            stroke-width="2"
                            fill="none"
                          />
                        </svg>
                      </div>
                    </div>
                  </div>
                  <!-- 查询向量 -->
                  <div class="query-vector-box">
                    <span class="query-label">查询向量（前10维）</span>
                    <div class="vector-preview-row">
                      <span
                        v-for="(val, vIdx) in (step.sample as QueryEncodingSample).query_vector_preview"
                        :key="vIdx"
                        class="vector-cell"
                        :class="val >= 0 ? 'positive' : 'negative'"
                      >{{ val }}</span>
                    </div>
                    <div class="vector-meta">
                      <span>维度: {{ (step.sample as QueryEncodingSample).query_vector_dimension }}</span>
                      <span>模型: {{ (step.sample as QueryEncodingSample).embedding_model }}</span>
                      <span>耗时: {{ (step.sample as QueryEncodingSample).encode_duration_ms }}ms</span>
                    </div>
                  </div>
                  <!-- 向量统计 -->
                  <div
                    v-if="(step.sample as QueryEncodingSample).vector_stats"
                    class="embedding-stats"
                  >
                    <div class="stat-item">
                      <span class="stat-label">最小值</span>
                      <span class="stat-value">{{ (step.sample as QueryEncodingSample).vector_stats.min }}</span>
                    </div>
                    <div class="stat-item">
                      <span class="stat-label">最大值</span>
                      <span class="stat-value">{{ (step.sample as QueryEncodingSample).vector_stats.max }}</span>
                    </div>
                    <div class="stat-item">
                      <span class="stat-label">均值</span>
                      <span class="stat-value">{{ (step.sample as QueryEncodingSample).vector_stats.mean }}</span>
                    </div>
                    <div class="stat-item">
                      <span class="stat-label">L2 范数</span>
                      <span class="stat-value">{{ (step.sample as QueryEncodingSample).vector_stats.norm }}</span>
                    </div>
                  </div>
                  <!-- 为什么用同一个模型 -->
                  <div class="knowledge-tip">
                    <span class="tip-icon">💡</span>
                    <span class="tip-text">{{ (step.sample as QueryEncodingSample).why_same_model }}</span>
                  </div>
                </div>
              </div>
              <div
                v-else
                class="empty-sample"
              >
                <p>向量库未构建，无法展示查询编码</p>
                <p class="empty-hint">
                  请先构建知识库，这里会展示用户问题如何被转换为向量
                </p>
              </div>
            </template>

            <!-- Retriever 相似度检索 -->
            <template v-if="step.step_info.name === 'retrieval'">
              <div
                v-if="step.sample"
                class="sample-section"
              >
                <h4 class="sample-title">
                  检索结果
                </h4>
                <div class="retrieval-config">
                  <el-tag
                    size="small"
                    type="primary"
                  >
                    Top-{{ (step.sample as RetrievalSample).top_k }}
                  </el-tag>
                  <el-tag
                    size="small"
                    type="info"
                  >
                    {{ (step.sample as RetrievalSample).distance_function }} 距离
                  </el-tag>
                  <el-tag
                    size="small"
                    type="success"
                  >
                    命中 {{ (step.sample as RetrievalSample).retrieved_count }} 个
                  </el-tag>
                  <el-tag
                    size="small"
                  >
                    总 Chunk: {{ (step.sample as RetrievalSample).total_chunks_in_store }}
                  </el-tag>
                  <el-tag
                    size="small"
                    type="warning"
                  >
                    耗时 {{ (step.sample as RetrievalSample).retrieval_duration_ms }}ms
                  </el-tag>
                </div>
                <!-- 相似度分布 -->
                <div
                  v-if="(step.sample as RetrievalSample).similarity_stats"
                  class="similarity-distribution"
                >
                  <span class="sim-label">相似度分布</span>
                  <div class="sim-bars">
                    <div
                      v-for="item in (step.sample as RetrievalSample).results"
                      :key="item.index"
                      class="sim-bar-item"
                    >
                      <span class="sim-bar-rank">#{{ item.index }}</span>
                      <div class="sim-bar-track">
                        <div
                          class="sim-bar-fill"
                          :style="{ width: (item.similarity * 100) + '%' }"
                        />
                      </div>
                      <span class="sim-bar-value">{{ (item.similarity * 100).toFixed(1) }}%</span>
                    </div>
                  </div>
                  <div class="sim-stats-row">
                    <span>最高: {{ ((step.sample as RetrievalSample).similarity_stats.max * 100).toFixed(1) }}%</span>
                    <span>最低: {{ ((step.sample as RetrievalSample).similarity_stats.min * 100).toFixed(1) }}%</span>
                    <span>平均: {{ ((step.sample as RetrievalSample).similarity_stats.avg * 100).toFixed(1) }}%</span>
                  </div>
                </div>
                <!-- 检索结果列表 -->
                <div class="retrieval-results">
                  <div
                    v-for="item in (step.sample as RetrievalSample).results"
                    :key="item.index"
                    class="retrieval-item"
                  >
                    <div
                      class="retrieval-item-header"
                      @click="toggleRetrieval(item.index)"
                    >
                      <span class="retrieval-rank">#{{ item.index }}</span>
                      <span class="retrieval-source">{{ item.source }}</span>
                      <div class="retrieval-score-bar">
                        <div
                          class="score-fill"
                          :style="{ width: (item.similarity * 100) + '%' }"
                        />
                      </div>
                      <span class="retrieval-score">{{ (item.similarity * 100).toFixed(1) }}%</span>
                      <span class="retrieval-expand-btn">
                        {{ expandedRetrieval.has(item.index) ? '收起' : '展开' }}
                      </span>
                    </div>
                    <div
                      v-if="expandedRetrieval.has(item.index)"
                      class="retrieval-item-content"
                    >
                      <p>{{ item.content_preview }}</p>
                      <div class="retrieval-item-meta">
                        <span>距离: {{ item.distance }}</span>
                        <span>文本长度: {{ item.content_length }} 字符</span>
                      </div>
                    </div>
                  </div>
                </div>
                <!-- 知识提示 -->
                <div class="knowledge-tip">
                  <span class="tip-icon">💡</span>
                  <span class="tip-text">{{ (step.sample as RetrievalSample).how_cosine_works }}</span>
                </div>
                <div class="knowledge-tip">
                  <span class="tip-icon">🎯</span>
                  <span class="tip-text">{{ (step.sample as RetrievalSample).why_top_k }}</span>
                </div>
              </div>
              <div
                v-else
                class="empty-sample"
              >
                <p>向量库未构建，无法展示检索结果</p>
                <p class="empty-hint">
                  请先构建知识库，这里会展示相似度检索的详细结果
                </p>
              </div>
            </template>

            <!-- Reranker 重排序 -->
            <template v-if="step.step_info.name === 'reranking'">
              <div
                v-if="step.sample"
                class="sample-section"
              >
                <h4 class="sample-title">
                  重排序配置
                </h4>
                <div class="reranking-info">
                  <div class="reranking-status">
                    <el-tag
                      :type="(step.sample as RerankingSample).enabled ? 'success' : 'warning'"
                      size="small"
                    >
                      {{ (step.sample as RerankingSample).enabled ? '已启用' : '未启用' }}
                    </el-tag>
                  </div>
                  <div class="reranking-details">
                    <div class="reranking-detail-item">
                      <span class="detail-label">模型</span>
                      <span class="detail-value mono">{{ (step.sample as RerankingSample).model }}</span>
                    </div>
                    <div class="reranking-detail-item">
                      <span class="detail-label">输出数量</span>
                      <span class="detail-value">Top-{{ (step.sample as RerankingSample).top_n }}</span>
                    </div>
                    <div class="reranking-detail-item">
                      <span class="detail-label">原理</span>
                      <span class="detail-value">{{ (step.sample as RerankingSample).description }}</span>
                    </div>
                    <div class="reranking-detail-item">
                      <span class="detail-label">输入</span>
                      <span class="detail-value">{{ (step.sample as RerankingSample).input_example }}</span>
                    </div>
                    <div class="reranking-detail-item">
                      <span class="detail-label">输出</span>
                      <span class="detail-value">{{ (step.sample as RerankingSample).output_example }}</span>
                    </div>
                  </div>

                  <!-- 重排序结果对比 -->
                  <div
                    v-if="(step.sample as RerankingSample).rerank_results"
                    class="rerank-results-section"
                  >
                    <h4
                      class="sample-title"
                      style="margin-top: 16px;"
                    >
                      重排序结果
                      <el-tag
                        size="small"
                        type="info"
                      >
                        耗时 {{ (step.sample as RerankingSample).rerank_results!.rerank_duration_ms }}ms
                      </el-tag>
                      <el-tag
                        size="small"
                        type="warning"
                      >
                        输入 {{ (step.sample as RerankingSample).rerank_results!.input_count }} → 输出 {{ (step.sample as RerankingSample).rerank_results!.output_count }}
                      </el-tag>
                    </h4>
                    <div class="rerank-comparison">
                      <!-- 重排序前 -->
                      <div class="rerank-column">
                        <span class="rerank-col-title">重排序前（Bi-Encoder 相似度）</span>
                        <div
                          v-for="item in (step.sample as RerankingSample).rerank_results!.before"
                          :key="'b' + item.rank"
                          class="rerank-item rerank-item-before"
                        >
                          <span class="rerank-item-rank">#{{ item.rank }}</span>
                          <span class="rerank-item-source">{{ item.source }}</span>
                          <span class="rerank-item-score">{{ (item.similarity * 100).toFixed(1) }}%</span>
                        </div>
                      </div>
                      <!-- 箭头 -->
                      <div class="rerank-arrow">
                        <svg
                          viewBox="0 0 24 24"
                          width="24"
                          height="24"
                        >
                          <path
                            d="M12 4v16m0 0l-6-6m6 6l6-6"
                            stroke="currentColor"
                            stroke-width="2"
                            fill="none"
                          />
                        </svg>
                      </div>
                      <!-- 重排序后 -->
                      <div class="rerank-column">
                        <span class="rerank-col-title">重排序后（Cross-Encoder 分数）</span>
                        <div
                          v-for="item in (step.sample as RerankingSample).rerank_results!.after"
                          :key="'a' + item.new_rank"
                          class="rerank-item rerank-item-after"
                        >
                          <span class="rerank-item-rank">#{{ item.new_rank }}</span>
                          <span class="rerank-item-source">{{ item.source }}</span>
                          <span class="rerank-item-score">{{ item.reranker_score.toFixed(4) }}</span>
                          <span
                            class="rerank-item-change"
                            :class="item.rank_change > 0 ? 'rank-up' : item.rank_change < 0 ? 'rank-down' : 'rank-same'"
                          >
                            {{ item.rank_change > 0 ? '↑' + item.rank_change : item.rank_change < 0 ? '↓' + Math.abs(item.rank_change) : '-' }}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>

                  <!-- Bi-Encoder vs Cross-Encoder 对比 -->
                  <div
                    v-if="(step.sample as RerankingSample).comparison"
                    class="encoder-comparison"
                  >
                    <span class="comparison-title">Bi-Encoder vs Cross-Encoder 对比</span>
                    <div class="comparison-table">
                      <div class="comparison-header">
                        <span class="comparison-col" />
                        <span class="comparison-col">{{ (step.sample as RerankingSample).comparison.bi_encoder.name }}</span>
                        <span class="comparison-col">{{ (step.sample as RerankingSample).comparison.cross_encoder.name }}</span>
                      </div>
                      <div class="comparison-row">
                        <span class="comparison-label">原理</span>
                        <span class="comparison-value">{{ (step.sample as RerankingSample).comparison.bi_encoder.how }}</span>
                        <span class="comparison-value">{{ (step.sample as RerankingSample).comparison.cross_encoder.how }}</span>
                      </div>
                      <div class="comparison-row">
                        <span class="comparison-label">速度</span>
                        <span class="comparison-value speed-fast">{{ (step.sample as RerankingSample).comparison.bi_encoder.speed }}</span>
                        <span class="comparison-value speed-slow">{{ (step.sample as RerankingSample).comparison.cross_encoder.speed }}</span>
                      </div>
                      <div class="comparison-row">
                        <span class="comparison-label">精度</span>
                        <span class="comparison-value acc-mid">{{ (step.sample as RerankingSample).comparison.bi_encoder.accuracy }}</span>
                        <span class="comparison-value acc-high">{{ (step.sample as RerankingSample).comparison.cross_encoder.accuracy }}</span>
                      </div>
                      <div class="comparison-row">
                        <span class="comparison-label">用途</span>
                        <span class="comparison-value">{{ (step.sample as RerankingSample).comparison.bi_encoder.use_case }}</span>
                        <span class="comparison-value">{{ (step.sample as RerankingSample).comparison.cross_encoder.use_case }}</span>
                      </div>
                    </div>
                  </div>
                  <div
                    v-if="(step.sample as RerankingSample).when_to_use"
                    class="knowledge-tip"
                  >
                    <span class="tip-icon">💡</span>
                    <span class="tip-text">{{ (step.sample as RerankingSample).when_to_use }}</span>
                  </div>
                  <div
                    v-if="!(step.sample as RerankingSample).enabled"
                    class="reranking-hint"
                  >
                    在系统设置中开启 Reranker，可提升检索精度
                  </div>
                </div>
              </div>
            </template>

            <!-- Prompt Builder 提示构建 -->
            <template v-if="step.step_info.name === 'prompt_building'">
              <div
                v-if="step.sample"
                class="sample-section"
              >
                <h4 class="sample-title">
                  Prompt 模板与拼装
                </h4>
                <div class="prompt-builder-sample">
                  <!-- 模板变量说明 -->
                  <div
                    v-if="(step.sample as PromptBuildingSample).template_variables?.length"
                    class="template-variables"
                  >
                    <span class="tv-label">模板变量</span>
                    <div class="tv-list">
                      <div
                        v-for="tv in (step.sample as PromptBuildingSample).template_variables"
                        :key="tv.name"
                        class="tv-item"
                      >
                        <code class="tv-name">{{ tv.name }}</code>
                        <span class="tv-desc">{{ tv.desc }}</span>
                        <span class="tv-source">来源: {{ tv.source }}</span>
                      </div>
                    </div>
                  </div>
                  <!-- Prompt 模板 -->
                  <div class="prompt-template-box">
                    <span class="prompt-label">Prompt 模板</span>
                    <pre class="prompt-template-code">{{ (step.sample as PromptBuildingSample).prompt_template }}</pre>
                  </div>
                  <!-- 拼装信息 -->
                  <div class="prompt-assemble-info">
                    <div class="assemble-item">
                      <span class="assemble-label">上下文文档数</span>
                      <span class="assemble-value">{{ (step.sample as PromptBuildingSample).context_documents }}</span>
                    </div>
                    <div class="assemble-item">
                      <span class="assemble-label">上下文字符数</span>
                      <span class="assemble-value">{{ (step.sample as PromptBuildingSample).context_characters }}</span>
                    </div>
                    <div class="assemble-item">
                      <span class="assemble-label">Prompt 总长度</span>
                      <span class="assemble-value">{{ (step.sample as PromptBuildingSample).prompt_full_length }} 字符</span>
                    </div>
                    <div class="assemble-item">
                      <span class="assemble-label">包含对话历史</span>
                      <span class="assemble-value">{{ (step.sample as PromptBuildingSample).has_history ? '是' : '否' }}</span>
                    </div>
                  </div>
                  <!-- 拼装后预览 -->
                  <div class="prompt-preview-box">
                    <span class="prompt-label">拼装后的 Prompt 预览</span>
                    <pre class="prompt-preview-code">{{ (step.sample as PromptBuildingSample).prompt_preview }}</pre>
                  </div>
                  <!-- 知识提示 -->
                  <div
                    v-if="(step.sample as PromptBuildingSample).why_prompt_engineering"
                    class="knowledge-tip"
                  >
                    <span class="tip-icon">💡</span>
                    <span class="tip-text">{{ (step.sample as PromptBuildingSample).why_prompt_engineering }}</span>
                  </div>
                </div>
              </div>
            </template>

            <!-- LLM 答案生成 -->
            <template v-if="step.step_info.name === 'llm_generation'">
              <div
                v-if="step.sample"
                class="sample-section"
              >
                <h4 class="sample-title">
                  LLM 模型配置
                </h4>
                <div class="llm-config-grid">
                  <div class="llm-config-item">
                    <span class="config-label">当前模型</span>
                    <span class="config-value">{{ (step.sample as LLMGenerationSample).model_display || (step.sample as LLMGenerationSample).model }}</span>
                  </div>
                  <div class="llm-config-item">
                    <span class="config-label">类型</span>
                    <el-tag
                      :type="(step.sample as LLMGenerationSample).model_type === 'local' ? 'warning' : 'success'"
                      size="small"
                    >
                      {{ (step.sample as LLMGenerationSample).model_type === 'local' ? '本地模型' : '云端模型' }}
                    </el-tag>
                  </div>
                  <div
                    v-if="(step.sample as LLMGenerationSample).description"
                    class="llm-config-item llm-config-wide"
                  >
                    <span class="config-label">描述</span>
                    <span class="config-value">{{ (step.sample as LLMGenerationSample).description }}</span>
                  </div>
                  <div
                    v-if="(step.sample as LLMGenerationSample).hf_model"
                    class="llm-config-item llm-config-wide"
                  >
                    <span class="config-label">HuggingFace 模型</span>
                    <span class="config-value mono">{{ (step.sample as LLMGenerationSample).hf_model }}</span>
                  </div>
                  <div
                    v-if="(step.sample as LLMGenerationSample).api_base"
                    class="llm-config-item llm-config-wide"
                  >
                    <span class="config-label">API 地址</span>
                    <span class="config-value mono">{{ (step.sample as LLMGenerationSample).api_base }}</span>
                  </div>
                  <div
                    v-if="(step.sample as LLMGenerationSample).api_model"
                    class="llm-config-item"
                  >
                    <span class="config-label">API 模型</span>
                    <span class="config-value mono">{{ (step.sample as LLMGenerationSample).api_model }}</span>
                  </div>
                  <div class="llm-config-item">
                    <span class="config-label">Temperature</span>
                    <span class="config-value">{{ (step.sample as LLMGenerationSample).temperature }}</span>
                  </div>
                  <div class="llm-config-item">
                    <span class="config-label">Max Tokens</span>
                    <span class="config-value">{{ (step.sample as LLMGenerationSample).max_tokens }}</span>
                  </div>
                  <div class="llm-config-item">
                    <span class="config-label">流式输出</span>
                    <el-tag
                      :type="(step.sample as LLMGenerationSample).supports_streaming ? 'success' : 'info'"
                      size="small"
                    >
                      {{ (step.sample as LLMGenerationSample).supports_streaming ? '支持' : '不支持' }}
                    </el-tag>
                  </div>
                </div>
                <!-- 生成过程 -->
                <div
                  v-if="(step.sample as LLMGenerationSample).generation_process?.length"
                  class="process-flow"
                  style="margin-top: 16px;"
                >
                  <span class="process-label">生成过程</span>
                  <div class="process-steps">
                    <div
                      v-for="(ps, psi) in (step.sample as LLMGenerationSample).generation_process"
                      :key="psi"
                      class="process-step-item"
                    >
                      <span class="process-step-text">{{ ps }}</span>
                      <svg
                        v-if="psi < (step.sample as LLMGenerationSample).generation_process.length - 1"
                        viewBox="0 0 24 24"
                        width="14"
                        height="14"
                        class="process-arrow"
                      >
                        <path
                          d="M12 4v16m0 0l-6-6m6 6l6-6"
                          stroke="currentColor"
                          stroke-width="2"
                          fill="none"
                        />
                      </svg>
                    </div>
                  </div>
                </div>
                <!-- 参数说明 -->
                <div class="param-explain">
                  <div
                    v-if="(step.sample as LLMGenerationSample).what_is_temperature"
                    class="knowledge-tip"
                  >
                    <span class="tip-icon">🌡️</span>
                    <span class="tip-text">{{ (step.sample as LLMGenerationSample).what_is_temperature }}</span>
                  </div>
                  <div
                    v-if="(step.sample as LLMGenerationSample).what_is_max_tokens"
                    class="knowledge-tip"
                  >
                    <span class="tip-icon">📏</span>
                    <span class="tip-text">{{ (step.sample as LLMGenerationSample).what_is_max_tokens }}</span>
                  </div>
                </div>
                <!-- 可用模型列表 -->
                <div
                  v-if="(step.sample as LLMGenerationSample).all_available_models?.length"
                  class="available-models"
                >
                  <span class="am-label">可用模型列表</span>
                  <div class="am-list">
                    <div
                      v-for="m in (step.sample as LLMGenerationSample).all_available_models"
                      :key="m.key"
                      class="am-item"
                      :class="{ 'am-active': m.key === (step.sample as LLMGenerationSample).model }"
                    >
                      <el-tag
                        :type="m.type === 'local' ? 'warning' : 'success'"
                        size="small"
                      >
                        {{ m.type === 'local' ? '本地' : '云端' }}
                      </el-tag>
                      <span class="am-name">{{ m.key }}</span>
                      <span class="am-desc">{{ m.name }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </template>

            <!-- 实现模块 -->
            <div class="step-module">
              <span class="module-label">实现模块</span>
              <code class="module-path">{{ step.step_info.module }}</code>
            </div>
          </div>
        </transition>

        <!-- 步骤间箭头 -->
        <div
          v-if="idx < querySteps.length - 1"
          class="step-connector"
        >
          <svg
            viewBox="0 0 24 24"
            width="20"
            height="20"
          >
            <path
              d="M12 4v16m0 0l-6-6m6 6l6-6"
              stroke="currentColor"
              stroke-width="2"
              fill="none"
            />
          </svg>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '../api'

// ---- 类型定义 ----

interface DocumentLoadingFile {
  name: string
  size: number
  extension: string
  type_label: string
}

interface DocumentLoadingSample {
  files: DocumentLoadingFile[]
  text_preview: string
  supported_extensions?: string[]
  loader_mapping?: Record<string, string>
  process_steps?: string[]
  why_metadata?: string
}

interface TextSplittingChunk {
  id: string
  content_preview: string
  content_length: number
  metadata: Record<string, unknown>
}

interface TextSplittingSample {
  source: string
  chunks: TextSplittingChunk[]
  total_chunks?: number
  total_sources?: number
  chunk_strategy?: string
  chunk_size?: number
  chunk_overlap?: number
  length_stats?: { min: number; max: number; avg: number; total: number }
  length_distribution?: Record<string, number>
  strategy_explanation?: Record<string, string>
  process_steps?: string[]
  why_overlap?: string
}

interface EmbeddingSample {
  chunk_id: string
  chunk_text?: string
  embedding_preview: number[]
  embedding_dimension: number
  model_name: string
  embedding_stats?: {
    min: number
    max: number
    mean: number
    norm: number
  }
  process_steps?: string[]
  why_embedding?: string
  what_is_dimension?: string
}

interface IndexStructureItem {
  source: string
  chunk_count: number
  chunk_ids: string[]
  /** @deprecated 旧版后端返回截断的 ID 预览，新版返回完整 chunk_ids */
  chunk_ids_preview?: string[]
}

interface VectorStoreSample {
  exists: boolean
  documents_count: number
  total_chunks: number
  embedding_model: string
  embedding_dimension: number
  chunk_strategy: string
  chunk_size: number
  chunk_overlap: number
  distance_function?: string
  storage_path?: string
  index_structure: IndexStructureItem[]
  process_steps?: string[]
  what_is_hnsw?: string
  why_cosine?: string
}

interface IngestionStep {
  step_info: {
    order: number
    name: string
    label: string
    description: string
    input_desc: string
    output_desc: string
    module: string
    config: Record<string, unknown>
  }
  sample: DocumentLoadingSample | TextSplittingSample | EmbeddingSample | VectorStoreSample | null
}

// ---- 在线查询阶段类型 ----

interface QueryEncodingSample {
  sample_question: string
  query_vector_preview: number[]
  query_vector_dimension: number
  embedding_model: string
  encode_duration_ms: number
  vector_stats: {
    min: number
    max: number
    mean: number
    norm: number
  }
  why_same_model: string
  process_steps: string[]
}

interface RetrievalResult {
  index: number
  source: string
  similarity: number
  distance: number
  content_preview: string
  content_length: number
}

interface RetrievalSample {
  top_k: number
  distance_function: string
  retrieved_count: number
  retrieval_duration_ms: number
  total_chunks_in_store: number
  results: RetrievalResult[]
  similarity_stats: {
    max: number
    min: number
    avg: number
  }
  how_cosine_works: string
  why_top_k: string
}

interface RerankingSample {
  enabled: boolean
  model: string
  top_n: number
  description: string
  input_example: string
  output_example: string
  comparison: {
    bi_encoder: {
      name: string
      how: string
      speed: string
      accuracy: string
      use_case: string
    }
    cross_encoder: {
      name: string
      how: string
      speed: string
      accuracy: string
      use_case: string
    }
  }
  when_to_use: string
  rerank_results?: {
    before: Array<{ rank: number; source: string; similarity: number }>
    after: Array<{ new_rank: number; old_rank: number; source: string; reranker_score: number; similarity: number; rank_change: number }>
    rerank_duration_ms: number
    input_count: number
    output_count: number
  }
}

interface PromptBuildingSample {
  prompt_template: string
  template_variables: Array<{ name: string; desc: string; source: string }>
  prompt_preview: string
  prompt_full_length: number
  context_documents: number
  context_characters: number
  has_history: boolean
  why_prompt_engineering: string
}

interface LLMGenerationSample {
  model: string
  model_display: string
  model_type: string
  temperature: number
  max_tokens: number
  runtime_class: string
  description: string
  hf_model: string
  api_base: string
  api_model: string
  supports_streaming: boolean
  generation_process: string[]
  what_is_temperature: string
  what_is_max_tokens: string
  all_available_models: Array<{ key: string; name: string; type: string }>
}

interface QueryStep {
  step_info: {
    order: number
    name: string
    label: string
    description: string
    input_desc: string
    output_desc: string
    module: string
    config: Record<string, unknown>
  }
  sample: QueryEncodingSample | RetrievalSample | RerankingSample | PromptBuildingSample | LLMGenerationSample | null
}

// ---- 数据 ----

const ingestionSteps = ref<IngestionStep[]>([])
const querySteps = ref<QueryStep[]>([])
const expandedSteps = ref<Set<string>>(new Set())
const expandedSources = ref<Set<string>>(new Set())
const expandedRetrieval = ref<Set<number>>(new Set())
const loading = ref(true)

/** 每个步骤的"大白话"解释 */
const plainDescMap: Record<string, string> = {
  document_loading: '把 PDF、Word 等文档变成电脑能读懂的纯文本',
  text_splitting: '把长文本切成小段落，方便后续检索和匹配',
  embedding: '把每段文字转换成一组数字（向量），让电脑能理解语义',
  vector_store: '把所有向量存进数据库，建立索引，方便快速搜索',
  query_encoding: '把用户的问题也转换成向量，才能和文档向量做比较',
  retrieval: '在向量库中找到和问题最相似的文档片段',
  reranking: '用更精确的模型重新排序检索结果，提升相关性',
  prompt_building: '把检索到的文档和问题组装成提示词，发给大模型',
  llm_generation: '大模型根据提示词生成最终答案',
}

// ---- 方法 ----

function toggleStep(name: string) {
  const newSet = new Set(expandedSteps.value)
  if (newSet.has(name)) {
    newSet.delete(name)
  } else {
    newSet.add(name)
  }
  expandedSteps.value = newSet
}

function hasSample(step: IngestionStep): boolean {
  return step.sample !== null && step.sample !== undefined
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatChunkStrategy(strategy: string): string {
  if (strategy === 'semantic') return '语义分块'
  if (strategy === 'recursive') return '递归字符分块'
  return strategy
}

function toggleSource(source: string) {
  const newSet = new Set(expandedSources.value)
  if (newSet.has(source)) {
    newSet.delete(source)
  } else {
    newSet.add(source)
  }
  expandedSources.value = newSet
}

function toggleRetrieval(index: number) {
  const newSet = new Set(expandedRetrieval.value)
  if (newSet.has(index)) {
    newSet.delete(index)
  } else {
    newSet.add(index)
  }
  expandedRetrieval.value = newSet
}

function getBarHeight(value: number, stats: { min: number; max: number }): number {
  const range = stats.max - stats.min
  if (range === 0) return 10
  const normalized = (value - stats.min) / range
  return Math.max(4, normalized * 40)
}

// ---- 生命周期 ----

onMounted(async () => {
  try {
    const [previewRes, queryRes] = await Promise.all([
      api.getIngestionPreview(),
      api.getQueryPreview(),
    ])
    ingestionSteps.value = previewRes.data.steps ?? []
    querySteps.value = queryRes.data.steps ?? []
    // 默认展开第一个步骤
    if (ingestionSteps.value.length > 0) {
      expandedSteps.value = new Set([ingestionSteps.value[0].step_info.name])
    }
  } catch {
    ingestionSteps.value = []
    querySteps.value = []
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.pipeline-page {
  max-width: 960px;
  margin: 0 auto;
  padding: 24px 20px 48px;
}

/* ---- 页面标题 ---- */
.page-header {
  margin-bottom: 32px;
}
.page-header h2 {
  margin: 0 0 8px;
  font-size: 22px;
  color: var(--text-primary);
}
.page-desc {
  color: var(--text-muted);
  font-size: 14px;
  margin: 0;
  line-height: 1.6;
}

/* ---- 分割线 ---- */
.section-divider {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin: 32px 0 20px;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.divider-text {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}
.divider-hint {
  font-size: 13px;
  color: var(--text-muted);
}

/* ---- 垂直步骤条 ---- */
.stepper {
  display: flex;
  flex-direction: column;
  gap: 0;
}
.stepper-item {
  display: flex;
  gap: 20px;
}

/* 左侧轨道 */
.stepper-rail {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
  width: 40px;
}
.stepper-node {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.06);
  border: 2px solid rgba(255, 255, 255, 0.15);
  transition: all 0.3s ease;
  flex-shrink: 0;
}
.stepper-node.node-active {
  background: rgba(64, 158, 255, 0.15);
  border-color: #409eff;
  box-shadow: 0 0 12px rgba(64, 158, 255, 0.25);
}
.stepper-node.node-completed {
  background: rgba(64, 158, 255, 0.1);
  border-color: rgba(64, 158, 255, 0.5);
}
.node-number {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-muted);
  transition: color 0.3s ease;
}
.stepper-node.node-active .node-number,
.stepper-node.node-completed .node-number {
  color: #409eff;
}

.stepper-line {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 100%;
  flex: 1;
  min-height: 24px;
  padding: 4px 0;
  color: rgba(255, 255, 255, 0.15);
  transition: color 0.3s ease;
}
.stepper-line.line-active {
  color: rgba(64, 158, 255, 0.4);
}
.line-arrow {
  flex: 1;
}

/* 右侧卡片 */
.stepper-card {
  flex: 1;
  margin-bottom: 16px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  overflow: hidden;
  transition: border-color 0.3s ease, box-shadow 0.3s ease;
}
.stepper-card.card-expanded {
  border-color: rgba(64, 158, 255, 0.3);
  box-shadow: 0 2px 16px rgba(64, 158, 255, 0.08);
}

.card-header {
  padding: 16px 20px;
  cursor: pointer;
  position: relative;
  transition: background 0.2s ease;
}
.card-header:hover {
  background: rgba(255, 255, 255, 0.02);
}
.card-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}
.card-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}
.sample-badge {
  flex-shrink: 0;
}
.card-plain-desc {
  margin: 0 0 10px;
  font-size: 13px;
  color: var(--text-muted);
  line-height: 1.5;
}
.card-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 13px;
  color: var(--text-secondary);
}
.meta-item {
  display: inline-flex;
  gap: 4px;
}
.meta-label {
  font-size: 12px;
  color: var(--text-muted);
  background: rgba(255, 255, 255, 0.06);
  padding: 1px 6px;
  border-radius: 3px;
}
.meta-arrow {
  color: var(--text-muted);
  font-size: 14px;
}
.expand-icon {
  position: absolute;
  top: 18px;
  right: 16px;
  color: var(--text-muted);
  transition: transform 0.3s ease;
  display: flex;
  align-items: center;
}
.expand-icon.icon-expanded {
  transform: rotate(180deg);
}

/* 卡片展开动画 */
.card-expand-enter-active,
.card-expand-leave-active {
  transition: all 0.3s ease;
  overflow: hidden;
}
.card-expand-enter-from,
.card-expand-leave-to {
  opacity: 0;
  max-height: 0;
  padding-top: 0;
  padding-bottom: 0;
}
.card-expand-enter-to,
.card-expand-leave-from {
  opacity: 1;
  max-height: 2000px;
}

.card-body {
  padding: 0 20px 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}
.step-description {
  margin: 14px 0 16px;
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.6;
}

/* ---- 数据样本通用 ---- */
.sample-section {
  margin-top: 4px;
}
.sample-title {
  margin: 16px 0 10px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 6px;
}
.sample-title:first-child {
  margin-top: 0;
}
.title-hint {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: rgba(64, 158, 255, 0.2);
  color: #409eff;
  font-size: 11px;
  font-weight: 700;
  cursor: help;
}

/* ---- Step 1: 文档加载 ---- */
.file-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.file-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
}
.file-icon {
  color: var(--text-muted);
  flex-shrink: 0;
}
.file-info {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}
.file-name {
  font-size: 14px;
  color: var(--text-primary);
  word-break: break-all;
}
.file-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.text-preview-block {
  background: rgba(0, 0, 0, 0.25);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 8px;
  padding: 14px 16px;
  overflow-x: auto;
}
.text-preview-content {
  margin: 0;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
  max-height: 200px;
  overflow-y: auto;
}

/* ---- Step 2: 文本分块 ---- */
.chunk-source {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 13px;
}
.chunk-source-label {
  color: var(--text-muted);
}
.chunk-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.chunk-card {
  padding: 12px 14px;
  border-radius: 8px;
  border-left: 3px solid transparent;
  background: rgba(255, 255, 255, 0.03);
}
.chunk-color-0 {
  border-left-color: #409eff;
}
.chunk-color-1 {
  border-left-color: #67c23a;
}
.chunk-color-2 {
  border-left-color: #e6a23c;
}
.chunk-color-3 {
  border-left-color: #f56c6c;
}
.chunk-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.chunk-id {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}
.chunk-preview {
  margin: 0 0 8px;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 80px;
  overflow-y: auto;
}
.chunk-meta {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.chunk-meta-tag {
  font-size: 11px !important;
}

/* ---- Step 3: 向量化 ---- */
.embedding-flow {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px;
  background: rgba(0, 0, 0, 0.15);
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.06);
}
.embedding-input,
.embedding-output {
  flex: 1;
  min-width: 0;
}
.embedding-label {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.embedding-text-box {
  padding: 10px 12px;
  background: rgba(64, 158, 255, 0.08);
  border: 1px solid rgba(64, 158, 255, 0.2);
  border-radius: 6px;
}
.embedding-chunk-id {
  font-size: 13px;
  color: #409eff;
  font-family: monospace;
  margin-bottom: 8px;
}
.embedding-chunk-text {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 120px;
  overflow-y: auto;
}
.text-ellipsis {
  color: var(--text-muted);
  font-style: italic;
}
.embedding-transform {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.transform-arrow {
  display: flex;
  align-items: center;
  color: var(--text-muted);
}
.arrow-line {
  width: 32px;
  height: 2px;
  background: linear-gradient(90deg, rgba(64, 158, 255, 0.3), rgba(64, 158, 255, 0.8));
}
.arrow-head {
  color: #409eff;
}
.transform-model {
  white-space: nowrap;
}
.embedding-vector-box {
  padding: 10px 12px;
  background: rgba(103, 194, 58, 0.08);
  border: 1px solid rgba(103, 194, 58, 0.2);
  border-radius: 6px;
  font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.8;
  word-break: break-all;
}
.vector-bracket {
  color: var(--text-muted);
}
.vector-value {
  transition: color 0.2s ease;
}
.vec-positive {
  color: #67c23a;
}
.vec-negative {
  color: #f56c6c;
}
.vector-comma {
  color: var(--text-muted);
  margin-right: 2px;
}
.vector-ellipsis {
  color: var(--text-muted);
}
.embedding-dim {
  margin-top: 8px;
}
.embedding-stats {
  display: flex;
  gap: 12px;
  margin-top: 10px;
  flex-wrap: wrap;
}
.stat-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 6px 10px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 6px;
  border: 1px solid rgba(255, 255, 255, 0.06);
}
.stat-label {
  font-size: 11px;
  color: var(--text-muted);
}
.stat-value {
  font-size: 13px;
  color: var(--text-primary);
  font-family: monospace;
}
.embedding-visual {
  margin-top: 10px;
}
.visual-label {
  font-size: 11px;
  color: var(--text-muted);
  display: block;
  margin-bottom: 6px;
}
.visual-bars {
  display: flex;
  align-items: flex-end;
  gap: 4px;
  height: 50px;
  padding: 4px 0;
}
.visual-bar-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  flex: 1;
  max-width: 24px;
}
.visual-bar {
  width: 100%;
  border-radius: 2px 2px 0 0;
  min-height: 2px;
  transition: height 0.3s ease;
}
.visual-bar-label {
  font-size: 9px;
  color: var(--text-muted);
  font-family: monospace;
}

/* ---- Step 4: 向量存储 ---- */
.store-status-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
}
.store-status-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 14px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
}
.store-status-icon {
  color: var(--text-muted);
  flex-shrink: 0;
  margin-top: 2px;
}
.store-status-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}
.store-status-label {
  font-size: 12px;
  color: var(--text-muted);
}
.store-status-value {
  font-size: 14px;
  color: var(--text-primary);
}
.mono {
  font-family: monospace;
  font-size: 13px;
  word-break: break-all;
}

/* ---- 实现模块 ---- */
.step-module {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}
.module-label {
  color: var(--text-muted);
}
.module-path {
  font-size: 12px;
  color: #67c23a;
  background: rgba(103, 194, 58, 0.1);
  padding: 2px 8px;
  border-radius: 4px;
  font-family: monospace;
}

/* ---- 索引结构可视化 ---- */
.index-structure {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.index-source-card {
  background: rgba(255, 255, 255, 0.02);
  border-radius: 8px;
  padding: 12px 16px;
  border-left: 3px solid rgba(64, 158, 255, 0.5);
}
.index-source-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  cursor: pointer;
}
.index-source-header:hover {
  opacity: 0.85;
}
.index-source-icon {
  color: var(--text-muted);
  display: flex;
  align-items: center;
}
.index-source-name {
  font-size: 13px;
  color: var(--text-primary);
  font-weight: 500;
  flex: 1;
}
.index-chunk-ids {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}
.index-chunk-id {
  font-size: 11px;
  font-family: monospace;
  color: var(--text-muted);
  background: rgba(64, 158, 255, 0.08);
  padding: 2px 6px;
  border-radius: 4px;
}
.index-chunk-more {
  font-size: 11px;
  color: var(--text-muted);
  font-style: italic;
}
.index-expand-btn {
  font-size: 12px;
  color: #409eff;
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 2px;
  cursor: pointer;
  white-space: nowrap;
}
.expand-arrow {
  transition: transform 0.3s ease;
}
.expand-arrow.arrow-up {
  transform: rotate(180deg);
}
.index-chunk-id-full {
  font-size: 10px;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ---- 空状态 ---- */
.empty-sample {
  text-align: center;
  padding: 24px 16px;
  background: rgba(255, 255, 255, 0.02);
  border-radius: 8px;
  border: 1px dashed rgba(255, 255, 255, 0.1);
}
.empty-sample p {
  margin: 0 0 6px;
  font-size: 14px;
  color: var(--text-secondary);
}
.empty-sample-inline {
  padding: 12px 16px;
  background: rgba(255, 255, 255, 0.02);
  border-radius: 6px;
  border: 1px dashed rgba(255, 255, 255, 0.1);
}
.empty-sample-inline p {
  margin: 0;
  font-size: 13px;
  color: var(--text-muted);
}
.empty-hint {
  font-size: 13px !important;
  color: var(--text-muted) !important;
}

/* ---- 在线查询阶段 ---- */

/* 查询阶段步骤容器（复用 ingestion-stages 类名） */
.ingestion-stages {
  display: flex;
  flex-direction: column;
  gap: 0;
}

/* 步骤卡片 */
.step-card {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  overflow: hidden;
  transition: border-color 0.3s ease, box-shadow 0.3s ease;
}

/* 步骤头部 */
.step-header {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 18px;
  cursor: pointer;
  transition: background 0.2s ease;
}
.step-header:hover {
  background: rgba(255, 255, 255, 0.02);
}

/* 步骤序号 */
.step-order {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.06);
  border: 2px solid rgba(255, 255, 255, 0.15);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 700;
  color: var(--text-muted);
  flex-shrink: 0;
}

/* 步骤标题区域 */
.step-title-area {
  flex: 1;
  min-width: 0;
}
.step-title {
  margin: 0 0 2px;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}
.step-plain-desc {
  margin: 0;
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.5;
}

/* 步骤右侧元信息 */
.step-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.step-meta .expand-icon {
  position: static;
  transition: transform 0.3s ease;
}
.step-meta .expand-icon.expanded {
  transform: rotate(180deg);
}

/* 步骤展开体 */
.step-body {
  padding: 0 18px 18px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

/* 步骤输入/输出 */
.step-io {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 12px 0;
  padding: 10px 14px;
  background: rgba(0, 0, 0, 0.15);
  border-radius: 8px;
}
.io-item {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 1;
  min-width: 0;
}
.io-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  background: rgba(255, 255, 255, 0.06);
  padding: 2px 8px;
  border-radius: 4px;
  flex-shrink: 0;
}
.io-text {
  font-size: 12px;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 步骤间连接箭头 */
.step-connector {
  display: flex;
  justify-content: center;
  padding: 6px 0;
  color: var(--text-muted);
}

/* 步骤展开动画 */
.step-expand-enter-active,
.step-expand-leave-active {
  transition: all 0.3s ease;
  overflow: hidden;
}
.step-expand-enter-from,
.step-expand-leave-to {
  opacity: 0;
  max-height: 0;
}
.step-expand-enter-to,
.step-expand-leave-from {
  opacity: 1;
  max-height: 2000px;
}

/* Query Encoding */
.query-encoding-sample {
  display: flex;
  flex-direction: column;
  gap: 12px;
  align-items: center;
}
.query-input-box,
.query-vector-box {
  width: 100%;
  padding: 12px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
}
.query-label {
  display: block;
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 6px;
}
.query-text {
  font-size: 15px;
  color: var(--text-primary);
  padding: 8px 12px;
  background: rgba(0, 212, 255, 0.06);
  border-radius: 6px;
  border-left: 3px solid rgba(0, 212, 255, 0.5);
}
.arrow-down-icon {
  color: var(--text-muted);
}
.vector-preview-row {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 8px;
}
.vector-cell {
  display: inline-block;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 11px;
  font-family: 'SF Mono', 'Fira Code', monospace;
}
.vector-cell.positive {
  background: rgba(103, 194, 58, 0.12);
  color: #67c23a;
}
.vector-cell.negative {
  background: rgba(245, 108, 108, 0.12);
  color: #f56c6c;
}
.vector-meta {
  display: flex;
  gap: 16px;
  font-size: 12px;
  color: var(--text-muted);
}

/* Retrieval */
.retrieval-config {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
}
.retrieval-results {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.retrieval-item {
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  overflow: hidden;
}
.retrieval-item-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  cursor: pointer;
  transition: background 0.2s;
}
.retrieval-item-header:hover {
  background: rgba(255, 255, 255, 0.04);
}
.retrieval-rank {
  font-size: 12px;
  font-weight: 700;
  color: var(--accent-primary);
  min-width: 24px;
}
.retrieval-source {
  font-size: 12px;
  color: var(--text-secondary);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.retrieval-score-bar {
  width: 80px;
  height: 6px;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 3px;
  overflow: hidden;
}
.score-fill {
  height: 100%;
  background: linear-gradient(90deg, #67c23a, #00d4ff);
  border-radius: 3px;
  transition: width 0.3s;
}
.retrieval-score {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
  min-width: 48px;
  text-align: right;
}
.retrieval-expand-btn {
  font-size: 11px;
  color: var(--text-muted);
  cursor: pointer;
}
.retrieval-item-content {
  padding: 8px 12px 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}
.retrieval-item-content p {
  margin: 0 0 6px;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
}
.retrieval-item-meta {
  font-size: 11px;
  color: var(--text-muted);
}

/* Reranking */
.reranking-info {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.reranking-status {
  margin-bottom: 4px;
}
.reranking-details {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.reranking-detail-item {
  display: flex;
  gap: 8px;
  align-items: baseline;
}
.detail-label {
  font-size: 12px;
  color: var(--text-muted);
  min-width: 60px;
  flex-shrink: 0;
}
.detail-value {
  font-size: 13px;
  color: var(--text-secondary);
}
.reranking-hint {
  font-size: 12px;
  color: #e6a23c;
  padding: 8px 12px;
  background: rgba(230, 162, 60, 0.08);
  border-radius: 6px;
}

/* Prompt Builder */
.prompt-builder-sample {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.prompt-template-box,
.prompt-preview-box {
  padding: 12px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
}
.prompt-label {
  display: block;
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 8px;
}
.prompt-template-code,
.prompt-preview-code {
  margin: 0;
  padding: 10px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 6px;
  font-size: 12px;
  font-family: 'SF Mono', 'Fira Code', monospace;
  color: var(--text-secondary);
  white-space: pre-wrap;
  word-break: break-all;
  line-height: 1.6;
  max-height: 200px;
  overflow-y: auto;
}
.prompt-assemble-info {
  display: flex;
  gap: 16px;
}
.assemble-item {
  display: flex;
  gap: 6px;
  align-items: center;
}
.assemble-label {
  font-size: 12px;
  color: var(--text-muted);
}
.assemble-value {
  font-size: 13px;
  color: var(--text-primary);
  font-weight: 600;
}

/* LLM Generation */
.llm-config-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 10px;
}
.llm-config-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 12px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
}
.llm-config-wide {
  grid-column: span 2;
}
.config-label {
  font-size: 11px;
  color: var(--text-muted);
}
.config-value {
  font-size: 13px;
  color: var(--text-primary);
  font-weight: 600;
}

/* 编码流程 / 生成过程 */
.process-flow {
  width: 100%;
  padding: 12px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
}
.process-label {
  display: block;
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 10px;
}
.process-steps {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.process-step-item {
  display: flex;
  align-items: center;
  gap: 8px;
}
.process-step-text {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
}
.process-arrow {
  color: var(--text-muted);
  flex-shrink: 0;
  margin-left: 4px;
}

/* 知识提示 */
.knowledge-tip {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px 14px;
  margin-top: 10px;
  background: rgba(64, 158, 255, 0.06);
  border: 1px solid rgba(64, 158, 255, 0.15);
  border-radius: 8px;
}
.tip-icon {
  flex-shrink: 0;
  font-size: 14px;
}
.tip-text {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.6;
}

/* 相似度分布 */
.similarity-distribution {
  margin: 12px 0;
  padding: 12px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
}
.sim-label {
  display: block;
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 10px;
}
.sim-bars {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.sim-bar-item {
  display: flex;
  align-items: center;
  gap: 8px;
}
.sim-bar-rank {
  font-size: 11px;
  color: var(--text-muted);
  min-width: 20px;
  text-align: right;
}
.sim-bar-track {
  flex: 1;
  height: 8px;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 4px;
  overflow: hidden;
}
.sim-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #409eff, #67c23a);
  border-radius: 4px;
  transition: width 0.3s;
}
.sim-bar-value {
  font-size: 11px;
  color: var(--text-primary);
  font-weight: 600;
  min-width: 40px;
  text-align: right;
}
.sim-stats-row {
  display: flex;
  gap: 16px;
  margin-top: 8px;
  font-size: 11px;
  color: var(--text-muted);
}

/* Encoder 对比表 */
.encoder-comparison {
  margin-top: 12px;
}

/* 重排序结果对比 */
.rerank-results-section {
  margin-top: 12px;
}
.rerank-comparison {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}
.rerank-column {
  flex: 1;
  min-width: 0;
}
.rerank-col-title {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  margin-bottom: 8px;
  text-align: center;
}
.rerank-arrow {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  padding-top: 28px;
  flex-shrink: 0;
}
.rerank-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-radius: 6px;
  margin-bottom: 4px;
  font-size: 12px;
}
.rerank-item-before {
  background: rgba(64, 158, 255, 0.06);
  border: 1px solid rgba(64, 158, 255, 0.15);
}
.rerank-item-after {
  background: rgba(103, 194, 58, 0.06);
  border: 1px solid rgba(103, 194, 58, 0.15);
}
.rerank-item-rank {
  font-weight: 700;
  color: var(--accent-primary);
  min-width: 24px;
}
.rerank-item-source {
  flex: 1;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.rerank-item-score {
  color: var(--text-primary);
  font-weight: 600;
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 11px;
}
.rerank-item-change {
  font-size: 11px;
  font-weight: 700;
  min-width: 24px;
  text-align: center;
}
.rank-up {
  color: #67c23a;
}
.rank-down {
  color: #f56c6c;
}
.rank-same {
  color: var(--text-muted);
}
.comparison-title {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8px;
}
.comparison-table {
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.08);
}
.comparison-header {
  display: grid;
  grid-template-columns: 60px 1fr 1fr;
  background: rgba(255, 255, 255, 0.06);
}
.comparison-row {
  display: grid;
  grid-template-columns: 60px 1fr 1fr;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}
.comparison-col {
  padding: 8px 10px;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-primary);
}
.comparison-label {
  padding: 8px 10px;
  font-size: 11px;
  color: var(--text-muted);
  background: rgba(255, 255, 255, 0.03);
}
.comparison-value {
  padding: 8px 10px;
  font-size: 11px;
  color: var(--text-secondary);
  line-height: 1.5;
}
.speed-fast {
  color: #67c23a;
}
.speed-slow {
  color: #e6a23c;
}
.acc-mid {
  color: #e6a23c;
}
.acc-high {
  color: #67c23a;
}

/* 模板变量 */
.template-variables {
  margin-bottom: 12px;
}
.tv-label {
  display: block;
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 8px;
}
.tv-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.tv-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
}
.tv-name {
  font-size: 12px;
  color: #409eff;
  background: rgba(64, 158, 255, 0.1);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: monospace;
}
.tv-desc {
  font-size: 12px;
  color: var(--text-secondary);
  flex: 1;
}
.tv-source {
  font-size: 11px;
  color: var(--text-muted);
}

/* 可用模型列表 */
.available-models {
  margin-top: 16px;
}
.am-label {
  display: block;
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 8px;
}
.am-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 6px;
}
.am-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid rgba(255, 255, 255, 0.06);
}
.am-item.am-active {
  border-color: rgba(64, 158, 255, 0.4);
  background: rgba(64, 158, 255, 0.06);
}
.am-name {
  font-size: 12px;
  color: var(--text-primary);
  font-weight: 600;
}
.am-desc {
  font-size: 11px;
  color: var(--text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ---- 响应式 ---- */
@media (max-width: 768px) {
  .pipeline-page {
    padding: 16px 12px 32px;
  }
  .stepper-item {
    gap: 12px;
  }
  .stepper-rail {
    width: 32px;
  }
  .stepper-node {
    width: 30px;
    height: 30px;
  }
  .node-number {
    font-size: 12px;
  }
  .card-header {
    padding: 12px 14px;
  }
  .card-body {
    padding: 0 14px 16px;
  }
  .embedding-flow {
    flex-direction: column;
    gap: 12px;
  }
  .transform-arrow {
    transform: rotate(90deg);
  }
  .store-status-grid {
    grid-template-columns: 1fr;
  }
  .query-stages {
    grid-template-columns: 1fr;
  }
}
</style>
