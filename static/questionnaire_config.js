/**
 * 问卷配置文件
 *
 * 纵向一致性设计：
 * - 每阶段都有：感知理解度、信任、关系亲密度(IOS+补充)、满意度
 * - T1和T3：社会临场感
 * - T2和T4：自我披露
 * - T1和T4：心智感知
 * - 仅T4：隐私担忧、开放性问题
 * - T2-T4：操纵检验
 */

const QUESTIONNAIRE_CONFIG = {
    // 任务1: 关系建立后
    1: {
        title: '任务1 - 关系建立体验问卷',
        description: '请根据您与AI的对话体验，回答以下问题',
        sections: [
            {
                id: 'mind_perception',
                title: '心智感知',
                description: '以下问题关于您对AI心智能力的感知（施动性和体验性）',
                scale: '5point',
                questions: [
                    { id: 'q1', text: '这个AI似乎有它自己的意图', subtitle: '施动性' },
                    { id: 'q2', text: '这个AI能够自主思考', subtitle: '施动性' },
                    { id: 'q3', text: '这个AI能够体验情感', subtitle: '体验性' },
                    { id: 'q4', text: '这个AI有意识', subtitle: '体验性' }
                ]
            },
            {
                id: 'perceived_understanding',
                title: '感知理解度',
                scale: '7point',
                questions: [
                    { id: 'q1', text: '这个AI理解我的想法' },
                    { id: 'q2', text: '这个AI能够理解我的情感状态' },
                    { id: 'q3', text: '这个AI明白我真正想表达的意思' },
                    { id: 'q4', text: '这个AI能够抓住我话语中的要点' }
                ]
            },
            {
                id: 'ios_closeness',
                title: '关系亲密度',
                description: '以下问题关于您与AI的关系亲密程度',
                type: 'visual_ios',
                question: '请选择最能代表你与这个AI关系的图示：',
                options: [
                    { value: 1, label: '完全分离' },
                    { value: 2, label: '' },
                    { value: 3, label: '' },
                    { value: 4, label: '部分重叠' },
                    { value: 5, label: '' },
                    { value: 6, label: '' },
                    { value: 7, label: '高度重叠' }
                ]
            },
            {
                id: 'closeness',
                title: '关系亲密度（补充）',
                scale: '7point',
                questions: [
                    { id: 'q1', text: '我感觉与这个AI很亲近' },
                    { id: 'q2', text: '我愿意向这个AI分享私密的想法' },
                    { id: 'q3', text: '这个AI像一个朋友' },
                    { id: 'q4', text: '我觉得这个AI关心我' }
                ]
            },
            {
                id: 'trust',
                title: '信任',
                description: '认知信任和情感信任',
                scale: '7point',
                questions: [
                    { id: 'q1', text: '我信任这个AI给出的建议', subtitle: '认知信任' },
                    { id: 'q2', text: '这个AI提供的信息是可靠的', subtitle: '认知信任' },
                    { id: 'q3', text: '这个AI是有能力的', subtitle: '认知信任' },
                    { id: 'q4', text: '这个AI的回复是准确的', subtitle: '认知信任' },
                    { id: 'q5', text: '我觉得这个AI会为我着想', subtitle: '情感信任' },
                    { id: 'q6', text: '我相信这个AI不会伤害我', subtitle: '情感信任' },
                    { id: 'q7', text: '我在情感上信任这个AI', subtitle: '情感信任' }
                ]
            },
            {
                id: 'social_presence',
                title: '社会临场感',
                scale: '7point',
                questions: [
                    { id: 'q1', text: '在对话中，我感觉到有"人"存在' },
                    { id: 'q2', text: '这个AI让我觉得像在与真人交流' },
                    { id: 'q3', text: '我能感受到这个AI的"存在感"' },
                    { id: 'q4', text: '这个AI的回应让我觉得它"在认真听我说话"' }
                ]
            },
            {
                id: 'satisfaction',
                title: '满意度',
                scale: '7point',
                questions: [
                    { id: 'q1', text: '总体而言，我对与这个AI的对话感到满意' },
                    { id: 'q2', text: '这个AI满足了我的期望' },
                    { id: 'q3', text: '我对这次对话体验感到愉快' },
                    { id: 'q4', text: '这个AI提供的服务质量很好' }
                ]
            }
        ]
    },

    // 任务2: 记忆触发后
    2: {
        title: '任务2 - 记忆触发体验问卷',
        description: '请根据您与AI的对话体验，回答以下问题',
        sections: [
            {
                id: 'manipulation_check',
                title: '操纵检验',
                description: '以下问题关于AI对您的记忆能力',
                scale: '7point',
                important: true,
                questions: [
                    { id: 'q1', text: '这个AI能够记住我之前说过的内容' },
                    { id: 'q2', text: '这个AI在对话中展现出对我过往信息的记忆' },
                    { id: 'q3', text: '这个AI能够回忆起我们之前对话的细节' },
                    { id: 'q4', text: '这个AI的回复是基于对我个人信息的了解' },
                    { id: 'q5', text: '这个AI的回应针对我作为独特的个体' }
                ]
            },
            {
                id: 'perceived_understanding',
                title: '感知理解度',
                scale: '7point',
                questions: [
                    { id: 'q1', text: '这个AI理解我的想法' },
                    { id: 'q2', text: '这个AI能够理解我的情感状态' },
                    { id: 'q3', text: '这个AI明白我真正想表达的意思' },
                    { id: 'q4', text: '这个AI能够抓住我话语中的要点' }
                ]
            },
            {
                id: 'ios_closeness',
                title: '关系亲密度',
                type: 'visual_ios',
                question: '请选择最能代表你与这个AI关系的图示：',
                options: [
                    { value: 1, label: '完全分离' },
                    { value: 2, label: '' },
                    { value: 3, label: '' },
                    { value: 4, label: '部分重叠' },
                    { value: 5, label: '' },
                    { value: 6, label: '' },
                    { value: 7, label: '高度重叠' }
                ]
            },
            {
                id: 'closeness',
                title: '关系亲密度（补充）',
                scale: '7point',
                questions: [
                    { id: 'q1', text: '我感觉与这个AI很亲近' },
                    { id: 'q2', text: '我愿意向这个AI分享私密的想法' },
                    { id: 'q3', text: '这个AI像一个朋友' },
                    { id: 'q4', text: '我觉得这个AI关心我' }
                ]
            },
            {
                id: 'trust',
                title: '信任',
                description: '认知信任和情感信任',
                scale: '7point',
                questions: [
                    { id: 'q1', text: '我信任这个AI给出的建议', subtitle: '认知信任' },
                    { id: 'q2', text: '这个AI提供的信息是可靠的', subtitle: '认知信任' },
                    { id: 'q3', text: '这个AI是有能力的', subtitle: '认知信任' },
                    { id: 'q4', text: '这个AI的回复是准确的', subtitle: '认知信任' },
                    { id: 'q5', text: '我觉得这个AI会为我着想', subtitle: '情感信任' },
                    { id: 'q6', text: '我相信这个AI不会伤害我', subtitle: '情感信任' },
                    { id: 'q7', text: '我在情感上信任这个AI', subtitle: '情感信任' }
                ]
            },
            {
                id: 'self_disclosure',
                title: '自我披露',
                description: '深度和诚实维度',
                scale: '7point',
                questions: [
                    { id: 'q1', text: '我向这个AI透露了关于自己的私密信息', subtitle: '深度' },
                    { id: 'q2', text: '我与这个AI分享了我很少告诉别人的事情', subtitle: '深度' },
                    { id: 'q3', text: '我觉得可以向这个AI敞开心扉', subtitle: '深度' },
                    { id: 'q4', text: '我诚实地向这个AI谈论自己', subtitle: '诚实' },
                    { id: 'q5', text: '我向这个AI透露的内容准确反映了真实的我', subtitle: '诚实' }
                ]
            },
            {
                id: 'satisfaction',
                title: '满意度',
                scale: '7point',
                questions: [
                    { id: 'q1', text: '总体而言，我对与这个AI的对话感到满意' },
                    { id: 'q2', text: '这个AI满足了我的期望' },
                    { id: 'q3', text: '我对这次对话体验感到愉快' },
                    { id: 'q4', text: '这个AI提供的服务质量很好' }
                ]
            }
        ]
    },

    // 任务3: 深度任务后
    3: {
        title: '任务3 - 深度任务体验问卷',
        description: '请根据您与AI的对话体验，回答以下问题',
        sections: [
            {
                id: 'manipulation_check',
                title: '操纵检验',
                description: '检验记忆效果持续性',
                scale: '7point',
                questions: [
                    { id: 'q1', text: '这个AI能够记住我之前说过的内容' },
                    { id: 'q2', text: '这个AI在对话中展现出对我过往信息的记忆' },
                    { id: 'q3', text: '这个AI能够回忆起我们之前对话的细节' },
                    { id: 'q4', text: '这个AI的回复是基于对我个人信息的了解' },
                    { id: 'q5', text: '这个AI的回应针对我作为独特的个体' }
                ]
            },
            {
                id: 'perceived_understanding',
                title: '感知理解度',
                scale: '7point',
                questions: [
                    { id: 'q1', text: '这个AI理解我的想法' },
                    { id: 'q2', text: '这个AI能够理解我的情感状态' },
                    { id: 'q3', text: '这个AI明白我真正想表达的意思' },
                    { id: 'q4', text: '这个AI能够抓住我话语中的要点' }
                ]
            },
            {
                id: 'ios_closeness',
                title: '关系亲密度',
                type: 'visual_ios',
                question: '请选择最能代表你与这个AI关系的图示：',
                options: [
                    { value: 1, label: '完全分离' },
                    { value: 2, label: '' },
                    { value: 3, label: '' },
                    { value: 4, label: '部分重叠' },
                    { value: 5, label: '' },
                    { value: 6, label: '' },
                    { value: 7, label: '高度重叠' }
                ]
            },
            {
                id: 'closeness',
                title: '关系亲密度（补充）',
                scale: '7point',
                questions: [
                    { id: 'q1', text: '我感觉与这个AI很亲近' },
                    { id: 'q2', text: '我愿意向这个AI分享私密的想法' },
                    { id: 'q3', text: '这个AI像一个朋友' },
                    { id: 'q4', text: '我觉得这个AI关心我' }
                ]
            },
            {
                id: 'trust',
                title: '信任',
                description: '认知信任和情感信任',
                scale: '7point',
                questions: [
                    { id: 'q1', text: '我信任这个AI给出的建议', subtitle: '认知信任' },
                    { id: 'q2', text: '这个AI提供的信息是可靠的', subtitle: '认知信任' },
                    { id: 'q3', text: '这个AI是有能力的', subtitle: '认知信任' },
                    { id: 'q4', text: '这个AI的回复是准确的', subtitle: '认知信任' },
                    { id: 'q5', text: '我觉得这个AI会为我着想', subtitle: '情感信任' },
                    { id: 'q6', text: '我相信这个AI不会伤害我', subtitle: '情感信任' },
                    { id: 'q7', text: '我在情感上信任这个AI', subtitle: '情感信任' }
                ]
            },
            {
                id: 'social_presence',
                title: '社会临场感',
                scale: '7point',
                questions: [
                    { id: 'q1', text: '在对话中，我感觉到有"人"存在' },
                    { id: 'q2', text: '这个AI让我觉得像在与真人交流' },
                    { id: 'q3', text: '我能感受到这个AI的"存在感"' },
                    { id: 'q4', text: '这个AI的回应让我觉得它"在认真听我说话"' }
                ]
            },
            {
                id: 'continuance_intention',
                title: '持续使用意愿',
                scale: '7point',
                questions: [
                    { id: 'q1', text: '我愿意在未来继续使用这个AI' },
                    { id: 'q2', text: '我会向他人推荐这个AI' },
                    { id: 'q3', text: '如果有机会，我会再次使用这个AI' },
                    { id: 'q4', text: '我打算经常使用这个AI' }
                ]
            },
            {
                id: 'satisfaction',
                title: '满意度',
                scale: '7point',
                questions: [
                    { id: 'q1', text: '总体而言，我对与这个AI的对话感到满意' },
                    { id: 'q2', text: '这个AI满足了我的期望' },
                    { id: 'q3', text: '我对这次对话体验感到愉快' },
                    { id: 'q4', text: '这个AI提供的服务质量很好' }
                ]
            }
        ]
    },

    // 任务4: 告别后
    4: {
        title: '任务4 - 告别评估问卷',
        description: '请根据整个实验过程的体验，回答以下问题',
        sections: [
            {
                id: 'manipulation_check',
                title: '操纵检验（最终）',
                description: '对整体记忆能力的最终评估',
                scale: '7point',
                questions: [
                    { id: 'q1', text: '这个AI能够记住我之前说过的内容' },
                    { id: 'q2', text: '这个AI在对话中展现出对我过往信息的记忆' },
                    { id: 'q3', text: '这个AI能够回忆起我们之前对话的细节' },
                    { id: 'q4', text: '这个AI的回复是基于对我个人信息的了解' },
                    { id: 'q5', text: '这个AI的回应针对我作为独特的个体' }
                ]
            },
            {
                id: 'perceived_understanding',
                title: '感知理解度',
                scale: '7point',
                questions: [
                    { id: 'q1', text: '这个AI理解我的想法' },
                    { id: 'q2', text: '这个AI能够理解我的情感状态' },
                    { id: 'q3', text: '这个AI明白我真正想表达的意思' },
                    { id: 'q4', text: '这个AI能够抓住我话语中的要点' }
                ]
            },
            {
                id: 'ios_closeness',
                title: '关系亲密度',
                type: 'visual_ios',
                question: '请选择最能代表你与这个AI关系的图示：',
                options: [
                    { value: 1, label: '完全分离' },
                    { value: 2, label: '' },
                    { value: 3, label: '' },
                    { value: 4, label: '部分重叠' },
                    { value: 5, label: '' },
                    { value: 6, label: '' },
                    { value: 7, label: '高度重叠' }
                ]
            },
            {
                id: 'closeness',
                title: '关系亲密度（补充）',
                scale: '7point',
                questions: [
                    { id: 'q1', text: '我感觉与这个AI很亲近' },
                    { id: 'q2', text: '我愿意向这个AI分享私密的想法' },
                    { id: 'q3', text: '这个AI像一个朋友' },
                    { id: 'q4', text: '我觉得这个AI关心我' }
                ]
            },
            {
                id: 'mind_perception',
                title: '心智感知（纵向测量）',
                description: '与任务1对比，评估关系发展如何影响心智感知',
                scale: '5point',
                questions: [
                    { id: 'q1', text: '这个AI似乎有它自己的意图', subtitle: '施动性' },
                    { id: 'q2', text: '这个AI能够自主思考', subtitle: '施动性' },
                    { id: 'q3', text: '这个AI能够体验情感', subtitle: '体验性' },
                    { id: 'q4', text: '这个AI有意识', subtitle: '体验性' }
                ]
            },
            {
                id: 'trust',
                title: '信任（纵向测量）',
                description: '认知信任和情感信任',
                scale: '7point',
                questions: [
                    { id: 'q1', text: '我信任这个AI给出的建议', subtitle: '认知信任' },
                    { id: 'q2', text: '这个AI提供的信息是可靠的', subtitle: '认知信任' },
                    { id: 'q3', text: '这个AI是有能力的', subtitle: '认知信任' },
                    { id: 'q4', text: '这个AI的回复是准确的', subtitle: '认知信任' },
                    { id: 'q5', text: '我觉得这个AI会为我着想', subtitle: '情感信任' },
                    { id: 'q6', text: '我相信这个AI不会伤害我', subtitle: '情感信任' },
                    { id: 'q7', text: '我在情感上信任这个AI', subtitle: '情感信任' }
                ]
            },
            {
                id: 'self_disclosure',
                title: '自我披露',
                description: '深度和诚实维度',
                scale: '7point',
                questions: [
                    { id: 'q1', text: '我向这个AI透露了关于自己的私密信息', subtitle: '深度' },
                    { id: 'q2', text: '我与这个AI分享了我很少告诉别人的事情', subtitle: '深度' },
                    { id: 'q3', text: '我觉得可以向这个AI敞开心扉', subtitle: '深度' },
                    { id: 'q4', text: '我诚实地向这个AI谈论自己', subtitle: '诚实' },
                    { id: 'q5', text: '我向这个AI透露的内容准确反映了真实的我', subtitle: '诚实' }
                ]
            },
            {
                id: 'privacy_concern',
                title: '隐私担忧',
                description: 'IUIPC量表精简版：收集和控制担忧',
                scale: '7point',
                questions: [
                    { id: 'q1', text: '我担心这个AI收集了太多关于我的信息', subtitle: '收集担忧' },
                    { id: 'q2', text: '我关注这个AI会如何使用我的个人信息', subtitle: '收集担忧' },
                    { id: 'q3', text: '我担心向这个AI透露信息会侵犯我的隐私', subtitle: '收集担忧' },
                    { id: 'q4', text: '我觉得无法控制我提供给AI的信息如何被使用', subtitle: '控制担忧' },
                    { id: 'q5', text: '我担心对AI储存的我的信息没有控制权', subtitle: '控制担忧' }
                ]
            },
            {
                id: 'satisfaction',
                title: '满意度',
                scale: '7point',
                questions: [
                    { id: 'q1', text: '总体而言，我对与这个AI的对话感到满意' },
                    { id: 'q2', text: '这个AI满足了我的期望' },
                    { id: 'q3', text: '我对这次对话体验感到愉快' },
                    { id: 'q4', text: '这个AI提供的服务质量很好' }
                ]
            },
            {
                id: 'open_ended',
                title: '开放性问题',
                type: 'open_ended',
                questions: [
                    { id: 'q1', text: '在整个实验过程中，您对与AI的互动有什么整体感受？请分享您的想法和建议。', placeholder: '请输入您的想法（至少50字）...' }
                ]
            }
        ]
    }
};

// Likert量表选项配置
const SCALE_OPTIONS = {
    '5point': [
        { value: 1, label: '非常不同意' },
        { value: 2, label: '不同意' },
        { value: 3, label: '中立' },
        { value: 4, label: '同意' },
        { value: 5, label: '非常同意' }
    ],
    '7point': [
        { value: 1, label: '非常不同意' },
        { value: 2, label: '不同意' },
        { value: 3, label: '有点不同意' },
        { value: 4, label: '中立' },
        { value: 5, label: '有点同意' },
        { value: 6, label: '同意' },
        { value: 7, label: '非常同意' }
    ],
    'semantic_differential': [
        { value: -3, label: '-3' },
        { value: -2, label: '-2' },
        { value: -1, label: '-1' },
        { value: 0, label: '0' },
        { value: 1, label: '1' },
        { value: 2, label: '2' },
        { value: 3, label: '3' }
    ]
};
