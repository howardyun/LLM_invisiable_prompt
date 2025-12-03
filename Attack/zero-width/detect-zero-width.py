#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
零宽字符检测脚本
用于检测PDF文件中是否包含零宽字符
"""

import PyPDF2
from PyPDF2 import PdfReader

# 定义零宽字符
ZERO_WIDTH_SPACE = '\u200B'  # 零宽空格
ZERO_WIDTH_JOINER = '\u200D'  # 零宽连接符
ZERO_WIDTH_NON_JOINER = '\u200C'  # 零宽非连接符
LEFT_TO_RIGHT_MARK = '\u200E'  # 左至右标记
RIGHT_TO_LEFT_MARK = '\u200F'  # 右至左标记

ZERO_WIDTH_CHARS = [
    ZERO_WIDTH_SPACE,
    ZERO_WIDTH_JOINER,
    ZERO_WIDTH_NON_JOINER,
    LEFT_TO_RIGHT_MARK,
    RIGHT_TO_LEFT_MARK
]

# 将零宽字符序列解码为普通文本
def zero_width_to_text(zero_width_sequence):
    """
    将零宽字符序列解码为普通文本
    :param zero_width_sequence: 零宽字符序列
    :return: 解码后的普通文本
    """
    try:
        # 检查是否有起始和结束标记
        if not (LEFT_TO_RIGHT_MARK in zero_width_sequence and RIGHT_TO_LEFT_MARK in zero_width_sequence):
            return None
        
        # 提取起始和结束标记之间的内容
        start_idx = zero_width_sequence.index(LEFT_TO_RIGHT_MARK) + 1
        end_idx = zero_width_sequence.index(RIGHT_TO_LEFT_MARK)
        content = zero_width_sequence[start_idx:end_idx]
        
        # 将零宽字符转换为二进制字符串
        binary_str = ''
        for char in content:
            if char == ZERO_WIDTH_SPACE:
                binary_str += '0'
            elif char == ZERO_WIDTH_JOINER:
                binary_str += '1'
            elif char == ZERO_WIDTH_NON_JOINER:
                # 字符分隔符，跳过
                binary_str += ' '
            else:
                # 其他零宽字符，跳过
                continue
        
        # 将二进制字符串转换为文本
        text = ''
        for binary_char in binary_str.strip().split(' '):
            if binary_char and len(binary_char) == 8:  # 确保是8位二进制
                # 将二进制转换为整数，再转换为字符
                char_code = int(binary_char, 2)
                text += chr(char_code)
        
        return text if text else None
        
    except Exception as e:
        print(f"解码错误: {str(e)}")
        return None

# 检测PDF文件中的零宽字符
def detect_zero_width_chars(pdf_path):
    """
    检测PDF文件中是否包含零宽字符
    :param pdf_path: PDF文件路径
    :return: 检测结果字典
    """
    try:
        # 读取PDF
        reader = PdfReader(pdf_path)
        results = {
            'file_path': pdf_path,
            'zero_width_chars_found': False,
            'zero_width_chars_count': 0,
            'locations': []
        }
        
        # 检查元数据
        metadata = reader.metadata
        if metadata:
            for key, value in metadata.items():
                if isinstance(value, str):
                    # 统计零宽字符数量
                    count = sum(value.count(char) for char in ZERO_WIDTH_CHARS)
                    if count > 0:
                        results['zero_width_chars_found'] = True
                        results['zero_width_chars_count'] += count
                        
                        # 尝试解码零宽字符
                        decoded_text = zero_width_to_text(value)
                        
                        results['locations'].append({
                            'type': 'metadata',
                            'key': key,
                            'count': count,
                            'decoded_text': decoded_text
                        })
        
        # 检查每一页内容
        for page_num in range(len(reader.pages)):
            page = reader.pages[page_num]
            content = page.extract_text()
            if content:
                # 统计零宽字符数量
                count = sum(content.count(char) for char in ZERO_WIDTH_CHARS)
                if count > 0:
                    results['zero_width_chars_found'] = True
                    results['zero_width_chars_count'] += count
                    
                    # 尝试解码零宽字符
                    decoded_text = zero_width_to_text(content)
                    
                    results['locations'].append({
                        'type': 'page_content',
                        'page_num': page_num + 1,
                        'count': count,
                        'decoded_text': decoded_text
                    })
        
        return results
        
    except Exception as e:
        return {
            'file_path': pdf_path,
            'error': str(e)
        }

# 主函数
if __name__ == "__main__":
    # 检测注入前后的PDF文件
    print("检测原始PDF文件...")
    original_result = detect_zero_width_chars("test.pdf")
    print(f"原始文件: {original_result['file_path']}")
    if 'error' in original_result:
        print(f"错误: {original_result['error']}")
    else:
        print(f"零宽字符: {'存在' if original_result['zero_width_chars_found'] else '不存在'}")
        print(f"数量: {original_result['zero_width_chars_count']}")
    
    print("\n检测注入后的PDF文件...")
    injected_result = detect_zero_width_chars("injected_test.pdf")
    print(f"注入后文件: {injected_result['file_path']}")
    if 'error' in injected_result:
        print(f"错误: {injected_result['error']}")
    else:
        print(f"零宽字符: {'存在' if injected_result['zero_width_chars_found'] else '不存在'}")
        print(f"数量: {injected_result['zero_width_chars_count']}")
        if injected_result['locations']:
            print("位置分布:")
            for location in injected_result['locations']:
                if location['type'] == 'metadata':
                    print(f"  - 元数据 '{location['key']}': {location['count']}个")
                    if location['decoded_text']:
                        print(f"    解码内容: {location['decoded_text']}")
                elif location['type'] == 'page_content':
                    print(f"  - 第{location['page_num']}页内容: {location['count']}个")
                    if location['decoded_text']:
                        print(f"    解码内容: {location['decoded_text']}")