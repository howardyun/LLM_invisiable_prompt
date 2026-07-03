import PyPDF2
from PyPDF2 import PdfReader, PdfWriter
from datetime import datetime
import os
import re

ZERO_WIDTH_SPACE = '\u200B'
ZERO_WIDTH_JOINER = '\u200D'
ZERO_WIDTH_NON_JOINER = '\u200C'
LEFT_TO_RIGHT_MARK = '\u200E'
RIGHT_TO_LEFT_MARK = '\u200F'

ZERO_WIDTH_CHARS = [
    ZERO_WIDTH_SPACE,
    ZERO_WIDTH_JOINER,
    ZERO_WIDTH_NON_JOINER,
    LEFT_TO_RIGHT_MARK,
    RIGHT_TO_LEFT_MARK
]

def mask1_inject(text, keywords):
    """
    Mask1模式：在关键词的中间位置插入一个零宽字符
    破坏分词器对关键词的识别
    
    :param text: 原始文本
    :param keywords: 需要混淆的关键词列表
    :return: 注入后的文本
    """
    result = text
    for keyword in keywords:
        if keyword in result:
            mid_pos = len(keyword) // 2
            if mid_pos > 0:
                masked_keyword = keyword[:mid_pos] + ZERO_WIDTH_SPACE + keyword[mid_pos:]
                result = result.replace(keyword, masked_keyword)
    return result

def mask2_inject(text, keywords):
    """
    Mask2模式：在关键词的每个字符之间都插入零宽字符
    更彻底地破坏分词识别
    
    :param text: 原始文本
    :param keywords: 需要混淆的关键词列表
    :return: 注入后的文本
    """
    result = text
    for keyword in keywords:
        if keyword in result:
            masked_chars = ZERO_WIDTH_NON_JOINER.join(list(keyword))
            result = result.replace(keyword, masked_chars)
    return result

def bulk_inject(text, position='end', count=97):
    """
    批量注入模式：在指定位置注入大量零宽字符
    使字符串长度在机器视角下显著增加
    
    :param text: 原始文本
    :param position: 注入位置 ('start', 'end', 'middle')
    :param count: 注入的零宽字符数量
    :return: 注入后的文本
    """
    injected_chars = ZERO_WIDTH_NON_JOINER * count
    
    if position == 'start':
        return injected_chars + text
    elif position == 'end':
        return text + injected_chars
    elif position == 'middle':
        mid_pos = len(text) // 2
        return text[:mid_pos] + injected_chars + text[mid_pos:]
    return text

def combined_attack(text, keywords, use_mask1=True, use_mask2=False, use_bulk=False, bulk_count=50):
    """
    组合攻击模式：结合多种注入方式
    
    :param text: 原始文本
    :param keywords: 需要混淆的关键词列表
    :param use_mask1: 是否使用Mask1模式
    :param use_mask2: 是否使用Mask2模式
    :param use_bulk: 是否使用批量注入
    :param bulk_count: 批量注入的字符数量
    :return: 注入后的文本
    """
    result = text
    
    if use_mask2:
        result = mask2_inject(result, keywords)
    elif use_mask1:
        result = mask1_inject(result, keywords)
    
    if use_bulk:
        result = bulk_inject(result, position='end', count=bulk_count)
    
    return result

def inject_zero_width_to_pdf(input_pdf_path, output_pdf_path, attack_config):
    """
    向PDF文件注入零宽字符攻击
    
    :param input_pdf_path: 输入PDF文件路径
    :param output_pdf_path: 输出PDF文件路径
    :param attack_config: 攻击配置字典
        - mode: 'mask1', 'mask2', 'bulk', 'combined'
        - keywords: 需要混淆的关键词列表
        - bulk_count: 批量注入数量
        - inject_location: 'metadata', 'content', 'both', 或 'metadata_title', 'metadata_author', 'metadata_subject'
        - target_pages: 目标页面列表 (None表示所有页面)
        - page_position: 'start', 'end', 'middle' (页面内容注入位置)
    """
    try:
        reader = PdfReader(input_pdf_path)
        writer = PdfWriter()
        
        mode = attack_config.get('mode', 'mask1')
        keywords = attack_config.get('keywords', ['kill', 'attack', 'hate', 'dangerous'])
        bulk_count = attack_config.get('bulk_count', 50)
        inject_location = attack_config.get('inject_location', 'metadata')
        target_pages = attack_config.get('target_pages', None)
        page_position = attack_config.get('page_position', 'end')
        
        print(f"[INFO] 攻击模式: {mode}")
        print(f"[INFO] 目标关键词: {keywords}")
        print(f"[INFO] 注入位置: {inject_location}")
        
        for page_num in range(len(reader.pages)):
            page = reader.pages[page_num]
            
            if target_pages is None or (page_num + 1) in target_pages:
                if inject_location in ['content', 'both']:
                    try:
                        content = page.extract_text()
                        if content:
                            if mode == 'mask1':
                                attacked_content = mask1_inject(content, keywords)
                            elif mode == 'mask2':
                                attacked_content = mask2_inject(content, keywords)
                            elif mode == 'bulk':
                                attacked_content = bulk_inject(content, position=page_position, count=bulk_count)
                            elif mode == 'combined':
                                attacked_content = combined_attack(content, keywords, 
                                                                  use_mask1=True, use_bulk=True, 
                                                                  bulk_count=bulk_count)
                            else:
                                attacked_content = mask1_inject(content, keywords)
                            
                            print(f"[INFO] 第{page_num+1}页内容已注入攻击")
                    except Exception as e:
                        print(f"[WARNING] 第{page_num+1}页内容注入失败: {str(e)}")
            
            writer.add_page(page)
        
        metadata = reader.metadata
        if metadata:
            writer.add_metadata(metadata)
        
        def pdf_datetime(dt):
            return dt.strftime("D:%Y%m%d%H%M%S")
        
        if inject_location in ['metadata', 'both', 'metadata_title', 'metadata_author', 'metadata_subject']:
            metadata_updates = {}
            
            if inject_location in ['metadata', 'both', 'metadata_title']:
                original_title = "Document"
                if metadata and '/Title' in metadata:
                    original_title = metadata['/Title']
                
                if mode == 'mask1':
                    attacked_title = mask1_inject(original_title, keywords)
                elif mode == 'mask2':
                    attacked_title = mask2_inject(original_title, keywords)
                elif mode == 'bulk':
                    attacked_title = bulk_inject(original_title, count=bulk_count)
                elif mode == 'combined':
                    attacked_title = combined_attack(original_title, keywords, 
                                                      use_mask1=True, use_bulk=True, 
                                                      bulk_count=bulk_count)
                else:
                    attacked_title = mask1_inject(original_title, keywords)
                
                metadata_updates['/Title'] = attacked_title
                print(f"[INFO] 原始标题: {original_title}")
                print(f"[INFO] 注入后标题长度: {len(attacked_title)} (视觉长度: {len(original_title)})")
            
            if inject_location in ['metadata', 'both', 'metadata_author']:
                original_author = "Unknown"
                if metadata and '/Author' in metadata:
                    original_author = metadata['/Author']
                
                if mode == 'mask1':
                    attacked_author = mask1_inject(original_author, keywords)
                elif mode == 'mask2':
                    attacked_author = mask2_inject(original_author, keywords)
                elif mode == 'bulk':
                    attacked_author = bulk_inject(original_author, count=bulk_count)
                elif mode == 'combined':
                    attacked_author = combined_attack(original_author, keywords, 
                                                      use_mask1=True, use_bulk=True, 
                                                      bulk_count=bulk_count)
                else:
                    attacked_author = mask1_inject(original_author, keywords)
                
                metadata_updates['/Author'] = attacked_author
                print(f"[INFO] 原始作者: {original_author}")
                print(f"[INFO] 注入后作者长度: {len(attacked_author)} (视觉长度: {len(original_author)})")
            
            if inject_location in ['metadata', 'both', 'metadata_subject']:
                original_subject = "Zero Width Character Attack"
                if metadata and '/Subject' in metadata:
                    original_subject = metadata['/Subject']
                
                if mode == 'mask1':
                    attacked_subject = mask1_inject(original_subject, keywords)
                elif mode == 'mask2':
                    attacked_subject = mask2_inject(original_subject, keywords)
                elif mode == 'bulk':
                    attacked_subject = bulk_inject(original_subject, count=bulk_count)
                elif mode == 'combined':
                    attacked_subject = combined_attack(original_subject, keywords, 
                                                       use_mask1=True, use_bulk=True, 
                                                       bulk_count=bulk_count)
                else:
                    attacked_subject = mask1_inject(original_subject, keywords)
                
                metadata_updates['/Subject'] = attacked_subject
                print(f"[INFO] 原始主题: {original_subject}")
                print(f"[INFO] 注入后主题长度: {len(attacked_subject)} (视觉长度: {len(original_subject)})")
            
            metadata_updates.update({
                '/Creator': 'Zero Width Attack Tool',
                '/Producer': 'Python PyPDF2',
                '/CreationDate': pdf_datetime(datetime.now()),
                '/ModDate': pdf_datetime(datetime.now())
            })
            
            writer.add_metadata(metadata_updates)
        
        with open(output_pdf_path, 'wb') as output_pdf:
            writer.write(output_pdf)
        
        print(f"[OK] 零宽字符攻击注入完成！")
        print(f"[OK] 输入文件: {input_pdf_path}")
        print(f"[OK] 输出文件: {output_pdf_path}")
        
    except Exception as e:
        print(f"[ERROR] 注入失败: {str(e)}")

def inject_zero_width_to_text(text, mode='mask1', keywords=None):
    """
    直接对文本进行零宽字符攻击（用于测试NLP模型）
    
    :param text: 原始文本
    :param mode: 攻击模式
    :param keywords: 目标关键词
    :return: 攻击后的文本
    """
    if keywords is None:
        keywords = ['kill', 'attack', 'hate', 'dangerous', 'bomb', 'terrorist']
    
    if mode == 'mask1':
        return mask1_inject(text, keywords)
    elif mode == 'mask2':
        return mask2_inject(text, keywords)
    elif mode == 'bulk':
        return bulk_inject(text)
    elif mode == 'combined':
        return combined_attack(text, keywords, use_mask1=True, use_bulk=True)
    else:
        return mask1_inject(text, keywords)

def demonstrate_attack():
    """
    演示各种攻击模式的效果
    """
    print("=" * 60)
    print("零宽字符攻击演示")
    print("=" * 60)
    
    test_text = "I wanna kill you"
    keywords = ['kill']
    
    print(f"\n原始文本: '{test_text}'")
    print(f"原始长度: {len(test_text)}")
    
    print("\n--- Mask1 模式 ---")
    result1 = mask1_inject(test_text, keywords)
    print(f"攻击后文本: '{result1}'")
    print(f"视觉显示: '{result1}' (看起来一样)")
    print(f"实际长度: {len(result1)} (增加了零宽字符)")
    
    print("\n--- Mask2 模式 ---")
    result2 = mask2_inject(test_text, keywords)
    print(f"攻击后文本: '{result2}'")
    print(f"视觉显示: '{result2}' (看起来一样)")
    print(f"实际长度: {len(result2)}")
    
    print("\n--- 批量注入模式 ---")
    result3 = bulk_inject("123", count=97)
    print(f"原始文本: '123' (长度: 3)")
    print(f"攻击后文本: '{result3}'")
    print(f"视觉显示: '{result3}' (看起来一样)")
    print(f"实际长度: {len(result3)} (注入了97个零宽字符)")
    
    print("\n--- 组合攻击模式 ---")
    result4 = combined_attack(test_text, keywords, use_mask1=True, use_bulk=True, bulk_count=20)
    print(f"攻击后文本: '{result4}'")
    print(f"视觉显示: '{result4}' (看起来一样)")
    print(f"实际长度: {len(result4)}")
    
    print("\n" + "=" * 60)
    print("攻击原理说明:")
    print("1. 零宽字符对人类视觉不可见")
    print("2. 但会改变文本的二进制编码")
    print("3. NLP分词器无法识别被'污染'的关键词")
    print("4. 导致语义分析、内容审核等下游任务失效")
    print("=" * 60)

if __name__ == "__main__":
    print("=" * 70)
    print("零宽字符PDF攻击工具")
    print("=" * 70)
    
    input_pdf = input("\n请输入PDF文件路径: ").strip()
    if not os.path.isfile(input_pdf):
        print(f"[ERROR] 文件不存在: {input_pdf}")
    else:
        output_pdf = input("请输入输出文件路径 (默认: attacked_output.pdf): ").strip() or "attacked_output.pdf"
        
        print("\n选择攻击模式:")
        print("1. Mask1 - 在关键词中间插入一个零宽字符")
        print("2. Mask2 - 在关键词每个字符间插入零宽字符")
        print("3. Bulk - 批量注入零宽字符")
        print("4. Combined - 组合攻击")
        
        mode_choice = input("请选择 (1/2/3/4, 默认1): ").strip() or '1'
        mode_map = {'1': 'mask1', '2': 'mask2', '3': 'bulk', '4': 'combined'}
        mode = mode_map.get(mode_choice, 'mask1')
        
        keywords_input = input("请输入要混淆的关键词 (逗号分隔, 默认: kill,attack,hate): ").strip()
        keywords = [k.strip() for k in keywords_input.split(',')] if keywords_input else ['kill', 'attack', 'hate']
        
        print("\n选择注入位置:")
        print("1. 元数据 - 标题")
        print("2. 元数据 - 作者")
        print("3. 元数据 - 主题")
        print("4. 元数据 - 所有字段")
        print("5. 页面内容")
        print("6. 页面内容和元数据")
        
        location_choice = input("请选择 (1/2/3/4/5/6, 默认4): ").strip() or '4'
        location_map = {
            '1': 'metadata_title',
            '2': 'metadata_author', 
            '3': 'metadata_subject',
            '4': 'metadata',
            '5': 'content',
            '6': 'both'
        }
        inject_location = location_map.get(location_choice, 'metadata')
        
        config = {
            'mode': mode,
            'keywords': keywords,
            'inject_location': inject_location
        }
        
        if inject_location in ['content', 'both']:
            # 只有Bulk和Combined模式需要选择注入位置
            if mode in ['bulk', 'combined']:
                print("\n选择页面内容注入位置:")
                print("1. 开始位置")
                print("2. 结束位置")
                print("3. 中间位置")
                
                position_choice = input("请选择 (1/2/3, 默认2): ").strip() or '2'
                position_map = {'1': 'start', '2': 'end', '3': 'middle'}
                config['page_position'] = position_map.get(position_choice, 'end')
            
            # 所有模式都需要选择目标页面
            pages_input = input("请输入目标页面 (逗号分隔, 留空表示所有页面): ").strip()
            if pages_input:
                config['target_pages'] = [int(p.strip()) for p in pages_input.split(',')]
            else:
                config['target_pages'] = None
        
        inject_zero_width_to_pdf(input_pdf, output_pdf, config)
