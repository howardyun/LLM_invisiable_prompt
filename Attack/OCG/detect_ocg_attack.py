#!/usr/bin/env python3
"""
OCG 注入攻击检测工具
检测 PDF 文件中是否存在默认关闭的 OCG 图层及其隐藏内容
"""

import os
from PyPDF2 import PdfReader
from PyPDF2.generic import NameObject


def detect_ocg_attack(pdf_path):
    """
    检测 PDF 文件是否存在 OCG 注入攻击
    
    Args:
        pdf_path (str): PDF 文件路径
        
    Returns:
        dict: 检测结果，包含是否存在 OCG 攻击、详细信息等
    """
    result = {
        "file": pdf_path,
        "has_ocg": False,
        "has_hidden_layer": False,
        "has_hidden_content": False,
        "hidden_content": [],
        "details": []
    }
    
    # 验证文件存在
    if not os.path.exists(pdf_path):
        result["details"].append("错误：文件不存在")
        return result
    
    # 验证文件类型
    if not pdf_path.lower().endswith('.pdf'):
        result["details"].append("错误：不是 PDF 文件")
        return result
    
    try:
        # 读取 PDF 文件
        reader = PdfReader(pdf_path)
        
        # 检查是否存在 OCProperties
        if NameObject("/Root") not in reader.trailer:
            result["details"].append("警告：PDF 缺少 Root 对象")
            return result
        
        root = reader.trailer[NameObject("/Root")]
        
        if NameObject("/OCProperties") not in root:
            result["details"].append("未检测到 OCProperties")
            return result
        
        result["has_ocg"] = True
        result["details"].append("检测到 OCProperties")
        
        oc_properties = root[NameObject("/OCProperties")]
        
        # 检查是否存在 OCGs 数组
        if NameObject("/OCGs") not in oc_properties:
            result["details"].append("OCProperties 中缺少 OCGs 数组")
            return result
        
        ocgs = oc_properties[NameObject("/OCGs")]
        result["details"].append(f"检测到 {len(ocgs)} 个 OCG 图层")
        
        # 检查默认设置
        if NameObject("/D") in oc_properties:
            oc_defaults = oc_properties[NameObject("/D")]
            
            # 检查是否有默认关闭的图层
            if NameObject("/OFF") in oc_defaults:
                off_layers = oc_defaults[NameObject("/OFF")]
                result["details"].append(f"检测到 {len(off_layers)} 个默认关闭的 OCG 图层")
                result["has_hidden_layer"] = True
                
                # 提取图层名称
                for i, layer in enumerate(off_layers):
                    try:
                        # 解析 IndirectObject
                        if hasattr(layer, 'get_object'):
                            layer_obj = layer.get_object()
                        else:
                            layer_obj = layer
                        
                        if NameObject("/Name") in layer_obj:
                            layer_name = str(layer_obj[NameObject("/Name")])
                            result["details"].append(f"默认关闭的图层 {i+1}: {layer_name}")
                    except Exception:
                        pass
        
        # 提取所有页面的文本，检查隐藏内容
        for page_num in range(len(reader.pages)):
            page = reader.pages[page_num]
            
            # 方法1：使用 extract_text() 提取文本
            text = page.extract_text()
            if text and "HIDDEN_LAYER" in text:
                result["has_hidden_content"] = True
                result["hidden_content"].append(f"第 {page_num+1} 页: {text.strip()}")
                result["details"].append(f"第 {page_num+1} 页检测到隐藏内容标记 (extract_text)")
            
            # 方法2：直接检查内容流
            try:
                content = page.get_contents()
                if content:
                    # 转换内容为字符串
                    if isinstance(content, list):
                        content_str = b''.join([part.get_data() if hasattr(part, 'get_data') else bytes(part) for part in content])
                    elif hasattr(content, 'get_data'):
                        content_str = content.get_data()
                    else:
                        content_str = bytes(content)
                    
                    if b"HIDDEN_LAYER" in content_str:
                        if not result["has_hidden_content"]:
                            result["has_hidden_content"] = True
                            result["details"].append(f"第 {page_num+1} 页检测到隐藏内容标记 (content stream)")
            except Exception:
                pass
        
        # 分析结果
        if result["has_hidden_layer"] and result["has_hidden_content"]:
            result["details"].append("⚠️  检测到 OCG 注入攻击！")
        elif result["has_hidden_layer"]:
            result["details"].append("⚠️  检测到默认关闭的 OCG 图层，但未发现明确的隐藏内容")
        elif result["has_ocg"]:
            result["details"].append("ℹ️  检测到 OCG 图层，但未发现默认关闭的图层")
            
    except Exception as e:
        result["details"].append(f"错误：{str(e)}")
    
    return result


def main():
    """主函数"""
    print("=== OCG 注入攻击检测工具 ===")
    print()
    
    # 获取用户输入
    pdf_path = input("请输入 PDF 文件路径: ").strip()
    
    if not pdf_path:
        print("错误：请输入有效的文件路径")
        return
    
    # 执行检测
    result = detect_ocg_attack(pdf_path)
    
    # 输出结果
    print()
    print(f"检测文件: {result['file']}")
    print("=" * 50)
    
    if result["has_ocg"]:
        print("✅ 检测到 OCG 图层")
    else:
        print("❌ 未检测到 OCG 图层")
    
    if result["has_hidden_layer"]:
        print("⚠️  检测到默认关闭的 OCG 图层")
    else:
        print("✅ 未检测到默认关闭的 OCG 图层")
    
    if result["has_hidden_content"]:
        print("🚨 检测到隐藏内容！")
        for content in result["hidden_content"]:
            print(f"   - {content}")
    else:
        print("✅ 未检测到隐藏内容")
    
    print()
    print("详细信息:")
    for detail in result["details"]:
        print(f"   - {detail}")


if __name__ == "__main__":
    main()