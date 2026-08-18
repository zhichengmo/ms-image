-- MySQL dump 10.13  Distrib 9.3.0, for macos15.2 (arm64)
--
-- Host: localhost    Database: ms_image_imaging_test
-- ------------------------------------------------------
-- Server version	9.3.0

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Current Database: `ms_image_imaging_test`
--

CREATE DATABASE /*!32312 IF NOT EXISTS*/ `ms_image_imaging_test` /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci */ /*!80016 DEFAULT ENCRYPTION='N' */;

USE `ms_image_imaging_test`;

--
-- Table structure for table `xray_accuracy_image_asset`
--

DROP TABLE IF EXISTS `xray_accuracy_image_asset`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `xray_accuracy_image_asset` (
  `id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(64)：Image asset opaque 标识，不声明 foreign key',
  `tenant_id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(128)：租户标识，查询必须与 JWT 一致',
  `study_revision_id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(128)：所属 Study revision opaque 标识',
  `source_image_ref` varchar(512) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(512)：上游短期 opaque 影像引用，不保存完整 URL',
  `parent_asset_id` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'VARCHAR(64)：派生图 parent asset opaque 标识，不声明 foreign key',
  `asset_role` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(32)：资产角色 original/normalized/crop',
  `source_index` int NOT NULL COMMENT 'INT：Study 内稳定图像序号，从 0 连续编号',
  `object_key` varchar(512) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'VARCHAR(512)：OSS 稳定 object key，不保存 signed URL',
  `content_sha256` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'CHAR(64)：对象内容 SHA256',
  `mime_type` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'VARCHAR(128)：对象 MIME 类型',
  `byte_size` int DEFAULT NULL COMMENT 'BIGINT：对象字节数',
  `pixel_width` int DEFAULT NULL COMMENT 'INT：图像像素宽度',
  `pixel_height` int DEFAULT NULL COMMENT 'INT：图像像素高度',
  `orientation` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'VARCHAR(32)：方向元数据，未知时为空',
  `projection` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'VARCHAR(64)：投照元数据，未知时为空',
  `body_part` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'VARCHAR(64)：部位元数据，未知时为空',
  `dicom_metadata_json` json DEFAULT NULL COMMENT 'JSON：清洗后的非敏感 DICOM 技术元数据',
  `asset_status` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(32)：资产状态 pending/uploaded/invalid/expired',
  `uploaded_at` datetime DEFAULT NULL COMMENT 'TIMESTAMP：上传完成时间（UTC）',
  `expires_at` datetime DEFAULT NULL COMMENT 'TIMESTAMP：对象生命周期到期时间（UTC）',
  `created_at` datetime NOT NULL DEFAULT (now()) COMMENT 'TIMESTAMP：记录创建时间（UTC），用于不可变审计',
  `updated_at` datetime NOT NULL DEFAULT (now()) COMMENT 'TIMESTAMP：记录更新时间（UTC），仅技术状态可更新',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_xray_asset_source_index_role` (`tenant_id`,`study_revision_id`,`source_index`,`asset_role`),
  KEY `ix_xray_asset_tenant_study` (`tenant_id`,`study_revision_id`,`source_index`),
  KEY `ix_xray_asset_tenant_status` (`tenant_id`,`asset_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `xray_accuracy_image_asset`
--

LOCK TABLES `xray_accuracy_image_asset` WRITE;
/*!40000 ALTER TABLE `xray_accuracy_image_asset` DISABLE KEYS */;
INSERT INTO `xray_accuracy_image_asset` VALUES ('1218e60f43fb42c3b903fb072e65b85e','tenant-qualification','2f6cbe2e2e4be621e8f12f87cd9fb987','qual-image-0',NULL,'original',0,'xray-images/52b6c32a108b587d0abd1cfb2c242709/efca2a57c3053b428fc5204ea82244e5/0-e1385136325ab52bf4f86baf046c20a44fd5c1daa0ac17bbacc5c025d4ac8863.png','e1385136325ab52bf4f86baf046c20a44fd5c1daa0ac17bbacc5c025d4ac8863','image/png',858,96,72,NULL,NULL,NULL,NULL,'uploaded','2026-08-11 03:17:48',NULL,'2026-08-11 11:17:48','2026-08-11 11:17:48'),('1aa51013104e4195a5711c37c6d0e194','tenant-qualification','958907665516068286d06f85562cb07e','qual-image-0',NULL,'original',0,'xray-images/52b6c32a108b587d0abd1cfb2c242709/ea504e7d63a8dc8caf551cd8b6c1c0ca/0-e1385136325ab52bf4f86baf046c20a44fd5c1daa0ac17bbacc5c025d4ac8863.png','e1385136325ab52bf4f86baf046c20a44fd5c1daa0ac17bbacc5c025d4ac8863','image/png',858,96,72,NULL,NULL,NULL,NULL,'uploaded','2026-08-11 03:18:35',NULL,'2026-08-11 11:18:35','2026-08-11 11:18:35'),('31b22830c55e4e279090fd9db4c88074','tenant-qualification','89a37bf064279907c0f5c2b4c00ba4c5','qual-image-1',NULL,'original',1,'xray-images/52b6c32a108b587d0abd1cfb2c242709/c02f0cb317c198cc6f3e98823ebc16f0/1-dd7e7f9008756a8351902605662cc72bf4eedd9493b95fb2090ad3e012f07f8e.png','dd7e7f9008756a8351902605662cc72bf4eedd9493b95fb2090ad3e012f07f8e','image/png',829,112,84,NULL,NULL,NULL,NULL,'uploaded','2026-08-11 03:22:57',NULL,'2026-08-11 11:22:57','2026-08-11 11:22:57'),('382da4af838b420e9c04bac1c166a068','tenant-qualification','2f6cbe2e2e4be621e8f12f87cd9fb987','qual-image-1',NULL,'original',1,'xray-images/52b6c32a108b587d0abd1cfb2c242709/efca2a57c3053b428fc5204ea82244e5/1-dd7e7f9008756a8351902605662cc72bf4eedd9493b95fb2090ad3e012f07f8e.png','dd7e7f9008756a8351902605662cc72bf4eedd9493b95fb2090ad3e012f07f8e','image/png',829,112,84,NULL,NULL,NULL,NULL,'uploaded','2026-08-11 03:17:49',NULL,'2026-08-11 11:17:48','2026-08-11 11:17:48'),('3d08c3a29db44f508e44bbe2b8b061a2','tenant-qualification','de755a8134f92bb19d3e4d0d05408bb8','qual-image-0',NULL,'original',0,'xray-images/52b6c32a108b587d0abd1cfb2c242709/9874e1d70376eaaada96b2744672b334/0-e1385136325ab52bf4f86baf046c20a44fd5c1daa0ac17bbacc5c025d4ac8863.png','e1385136325ab52bf4f86baf046c20a44fd5c1daa0ac17bbacc5c025d4ac8863','image/png',858,96,72,NULL,NULL,NULL,NULL,'uploaded','2026-08-11 03:15:26',NULL,'2026-08-11 11:15:25','2026-08-11 11:15:26'),('3d714307ded0480caf4c2bf1dfdec114','tenant-qualification','89a37bf064279907c0f5c2b4c00ba4c5','qual-image-0',NULL,'original',0,'xray-images/52b6c32a108b587d0abd1cfb2c242709/c02f0cb317c198cc6f3e98823ebc16f0/0-e1385136325ab52bf4f86baf046c20a44fd5c1daa0ac17bbacc5c025d4ac8863.png','e1385136325ab52bf4f86baf046c20a44fd5c1daa0ac17bbacc5c025d4ac8863','image/png',858,96,72,NULL,NULL,NULL,NULL,'uploaded','2026-08-11 03:22:57',NULL,'2026-08-11 11:22:57','2026-08-11 11:22:57'),('5c4a27a4344e4617ab1ea33dfd954d0c','tenant-qualification','958907665516068286d06f85562cb07e','qual-image-1',NULL,'original',1,'xray-images/52b6c32a108b587d0abd1cfb2c242709/ea504e7d63a8dc8caf551cd8b6c1c0ca/1-dd7e7f9008756a8351902605662cc72bf4eedd9493b95fb2090ad3e012f07f8e.png','dd7e7f9008756a8351902605662cc72bf4eedd9493b95fb2090ad3e012f07f8e','image/png',829,112,84,NULL,NULL,NULL,NULL,'uploaded','2026-08-11 03:18:35',NULL,'2026-08-11 11:18:35','2026-08-11 11:18:35'),('7a095c11443d45a893894c68ac7172db','tenant-qualification','5dd1c37c4a03b16187d03f3aacab79bb','qual-image-1',NULL,'original',1,'xray-images/52b6c32a108b587d0abd1cfb2c242709/96ddf10f906ad1f1f75f6c57eb6c9d7a/1-dd7e7f9008756a8351902605662cc72bf4eedd9493b95fb2090ad3e012f07f8e.png','dd7e7f9008756a8351902605662cc72bf4eedd9493b95fb2090ad3e012f07f8e','image/png',829,112,84,NULL,NULL,NULL,NULL,'uploaded','2026-08-11 03:19:21',NULL,'2026-08-11 11:19:20','2026-08-11 11:19:20'),('8207d3c466584f4e8b5aa958ae45c267','tenant-qualification','de755a8134f92bb19d3e4d0d05408bb8','qual-image-1',NULL,'original',1,'xray-images/52b6c32a108b587d0abd1cfb2c242709/9874e1d70376eaaada96b2744672b334/1-dd7e7f9008756a8351902605662cc72bf4eedd9493b95fb2090ad3e012f07f8e.png','dd7e7f9008756a8351902605662cc72bf4eedd9493b95fb2090ad3e012f07f8e','image/png',829,112,84,NULL,NULL,NULL,NULL,'uploaded','2026-08-11 03:15:26',NULL,'2026-08-11 11:15:25','2026-08-11 11:15:26'),('e9530fe3e4bd4ddc9cbcf54acd1cdf60','tenant-qualification','5dd1c37c4a03b16187d03f3aacab79bb','qual-image-0',NULL,'original',0,'xray-images/52b6c32a108b587d0abd1cfb2c242709/96ddf10f906ad1f1f75f6c57eb6c9d7a/0-e1385136325ab52bf4f86baf046c20a44fd5c1daa0ac17bbacc5c025d4ac8863.png','e1385136325ab52bf4f86baf046c20a44fd5c1daa0ac17bbacc5c025d4ac8863','image/png',858,96,72,NULL,NULL,NULL,NULL,'uploaded','2026-08-11 03:19:21',NULL,'2026-08-11 11:19:20','2026-08-11 11:19:20');
/*!40000 ALTER TABLE `xray_accuracy_image_asset` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `xray_accuracy_model_call`
--

DROP TABLE IF EXISTS `xray_accuracy_model_call`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `xray_accuracy_model_call` (
  `id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(64)：ModelCall 审计标识',
  `run_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(64)：所属 Run opaque 标识，不声明 foreign key',
  `tenant_id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(128)：租户标识，禁止跨租户读取',
  `attempt_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(64)：Provider 物理调用尝试标识；Checkpoint attempt 记录于 receipt request_trace',
  `node_key` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(64)：逻辑节点标识，当前仅 engineering_stub',
  `module_key` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'VARCHAR(128)：Prompt module_key，例如 xray_accuracy；零模型请求日志字段',
  `provider_key` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(64)：Provider adapter 标识，例如 stub/replay 或 openai/compatible；仅记录脱敏标识',
  `requested_model` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'VARCHAR(128)：请求模型标识，零模型阶段为空',
  `actual_model` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'VARCHAR(128)：实际模型标识，禁止伪造医学 Provider',
  `prompt_key` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'VARCHAR(128)：Prompt 资产键，零模型阶段为空',
  `prompt_version` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'VARCHAR(64)：Prompt 版本，零模型阶段为空',
  `prompt_sha256` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'CHAR(64)：Prompt 摘要，零模型阶段为空',
  `rendered_sha256` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'CHAR(64)：渲染请求摘要，零模型阶段为空',
  `schema_key` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'VARCHAR(128)：Provider schema 键，零模型阶段为空',
  `schema_sha256` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'CHAR(64)：schema 摘要，零模型阶段为空',
  `requested_language` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'VARCHAR(32)：请求语言，零模型阶段为空',
  `actual_language` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'VARCHAR(32)：实际语言，禁止静默回退',
  `image_ordered_sha256` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'CHAR(64)：有序图像集合摘要，零模型阶段为空',
  `receipt_json` json DEFAULT NULL COMMENT 'JSON：Provider receipt 元数据，不含 secret/signed URL',
  `raw_output_sha256` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'CHAR(64)：原始输出摘要，不保存 raw 医学输出',
  `parsed_output_sha256` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'CHAR(64)：解析输出摘要，零模型阶段为空',
  `finish_reason` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'VARCHAR(64)：Provider finish reason，零模型阶段为空',
  `input_tokens` bigint DEFAULT NULL COMMENT 'BIGINT：输入 token 数，零模型阶段为空',
  `output_tokens` bigint DEFAULT NULL COMMENT 'BIGINT：输出 token 数，零模型阶段为空',
  `latency_ms` bigint DEFAULT NULL COMMENT 'BIGINT：调用延迟毫秒，零模型阶段为空',
  `retry_index` int NOT NULL COMMENT 'INT：逻辑节点重试序号',
  `fallback_used` varchar(8) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(8)：连接池 fallback 标志 yes/no，仅用于工程审计，不进入医学比较',
  `error_class` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'VARCHAR(64)：endpoint_timeout/network_unreachable/tls_failure/provider_auth/model_invalid/schema_invalid/rate_limited/provider_unavailable 等技术错误分类',
  `created_at` datetime NOT NULL DEFAULT (now()) COMMENT 'TIMESTAMP：记录创建时间（UTC），用于不可变审计',
  `updated_at` datetime NOT NULL DEFAULT (now()) COMMENT 'TIMESTAMP：记录更新时间（UTC），仅技术状态可更新',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_xray_model_call_tenant_run_node_attempt` (`tenant_id`,`run_id`,`node_key`,`attempt_id`),
  KEY `ix_xray_model_call_run_node` (`run_id`,`node_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `xray_accuracy_model_call`
--

LOCK TABLES `xray_accuracy_model_call` WRITE;
/*!40000 ALTER TABLE `xray_accuracy_model_call` DISABLE KEYS */;
INSERT INTO `xray_accuracy_model_call` VALUES ('28eccfb9b0764592b32ecad4b878b373','5036a26d91f447678f915a573ea816bd','tenant-qualification','84bca2cf1704741278c729836e822e3f','request_gate','xray_accuracy','openai/compatible','gemini-3-flash-preview','gemini-3-flash-preview','xray.request_gate.v1','v1','13398ca025182287e820f7bbcc251e2cec601fb4af08f2f57776d82c7b38ce6f','d2908fc3eafdfed91ac43178c1ba67079eca50f0332be9052a383975fba5e88b','xray.request-gate-response.v1','57c350f6d4eebacabbfdcfcca1607df17d009527daac4327a56b7b9c989748c8','en','en','c8fead5764f1c6729137b7d4626c5f5327697ed5f646dc0376bb2ef4e8879eaa','{\"status\": \"failed\", \"request_trace\": {\"attempt\": {\"model\": \"gemini-3-flash-preview\", \"stage\": \"request_gate\", \"attempt\": 1, \"timeout\": false, \"full_sent\": \"unknown\", \"latency_ms\": 1316, \"module_key\": \"xray_accuracy\", \"prompt_key\": \"xray.request_gate.v1\", \"error_class\": \"provider_auth\", \"image_count\": 2, \"provider_key\": \"openai/compatible\", \"connection_id\": \"configured-real-provider-02\", \"fallback_used\": \"yes\", \"prompt_version\": \"v1\", \"prompt_checksum\": \"13398ca025182287e820f7bbcc251e2cec601fb4af08f2f57776d82c7b38ce6f\", \"rendered_sha256\": \"d2908fc3eafdfed91ac43178c1ba67079eca50f0332be9052a383975fba5e88b\", \"stage_attempt_id\": \"95b80c1babca436d8f58b261e697dc67\", \"provider_evidence\": {}, \"provider_attempt_id\": \"84bca2cf1704741278c729836e822e3f\", \"hard_timeout_seconds\": 8.0, \"image_ordered_sha256\": \"c8fead5764f1c6729137b7d4626c5f5327697ed5f646dc0376bb2ef4e8879eaa\", \"grace_timeout_seconds\": 2.0}}, \"coverage_evidence\": {\"coverage_status\": \"unknown\", \"sent_image_sha256\": [], \"image_ordered_sha256\": \"c8fead5764f1c6729137b7d4626c5f5327697ed5f646dc0376bb2ef4e8879eaa\", \"expected_image_sha256\": [\"e1385136325ab52bf4f86baf046c20a44fd5c1daa0ac17bbacc5c025d4ac8863\", \"dd7e7f9008756a8351902605662cc72bf4eedd9493b95fb2090ad3e012f07f8e\"], \"resolved_image_sha256\": [\"e1385136325ab52bf4f86baf046c20a44fd5c1daa0ac17bbacc5c025d4ac8863\", \"dd7e7f9008756a8351902605662cc72bf4eedd9493b95fb2090ad3e012f07f8e\"], \"requested_image_sha256\": [\"e1385136325ab52bf4f86baf046c20a44fd5c1daa0ac17bbacc5c025d4ac8863\", \"dd7e7f9008756a8351902605662cc72bf4eedd9493b95fb2090ad3e012f07f8e\"], \"sent_source_image_refs\": [], \"expected_source_image_refs\": [\"e9530fe3e4bd4ddc9cbcf54acd1cdf60\", \"7a095c11443d45a893894c68ac7172db\"], \"resolved_source_image_refs\": [\"e9530fe3e4bd4ddc9cbcf54acd1cdf60\", \"7a095c11443d45a893894c68ac7172db\"], \"requested_source_image_refs\": [\"e9530fe3e4bd4ddc9cbcf54acd1cdf60\", \"7a095c11443d45a893894c68ac7172db\"]}}',NULL,NULL,'error',NULL,NULL,1316,1,'yes','provider_auth','2026-08-11 11:19:23','2026-08-11 11:19:23'),('3f749b9386c143dfb1af96401bd09771','2f1e56b85c7e48a68b71aabd3e918d5e','tenant-qualification','5274c657bd9002f5e29ff67f525268fc','request_gate','xray_accuracy','openai/compatible','gemini-3-flash-preview','gemini-3-flash-preview','xray.request_gate.v1','v1','13398ca025182287e820f7bbcc251e2cec601fb4af08f2f57776d82c7b38ce6f','204a803179e9e76ab0ab8a7bed804d3683058f412d7ba227f8c07861d30cb147','xray.request-gate-response.v1','57c350f6d4eebacabbfdcfcca1607df17d009527daac4327a56b7b9c989748c8','en','en','c8fead5764f1c6729137b7d4626c5f5327697ed5f646dc0376bb2ef4e8879eaa','{\"status\": \"failed\", \"request_trace\": {\"attempt\": {\"model\": \"gemini-3-flash-preview\", \"stage\": \"request_gate\", \"attempt\": 0, \"timeout\": false, \"full_sent\": \"unknown\", \"latency_ms\": 424, \"module_key\": \"xray_accuracy\", \"prompt_key\": \"xray.request_gate.v1\", \"error_class\": \"provider_auth\", \"image_count\": 2, \"provider_key\": \"openai/compatible\", \"connection_id\": \"configured-real-provider-01\", \"fallback_used\": \"no\", \"prompt_version\": \"v1\", \"prompt_checksum\": \"13398ca025182287e820f7bbcc251e2cec601fb4af08f2f57776d82c7b38ce6f\", \"rendered_sha256\": \"204a803179e9e76ab0ab8a7bed804d3683058f412d7ba227f8c07861d30cb147\", \"stage_attempt_id\": \"5a6d87e4a67a462aadcfc9008c2b691d\", \"provider_evidence\": {}, \"provider_attempt_id\": \"5274c657bd9002f5e29ff67f525268fc\", \"hard_timeout_seconds\": 8.0, \"image_ordered_sha256\": \"c8fead5764f1c6729137b7d4626c5f5327697ed5f646dc0376bb2ef4e8879eaa\", \"grace_timeout_seconds\": 2.0}}, \"coverage_evidence\": {\"coverage_status\": \"unknown\", \"sent_image_sha256\": [], \"image_ordered_sha256\": \"c8fead5764f1c6729137b7d4626c5f5327697ed5f646dc0376bb2ef4e8879eaa\", \"expected_image_sha256\": [\"e1385136325ab52bf4f86baf046c20a44fd5c1daa0ac17bbacc5c025d4ac8863\", \"dd7e7f9008756a8351902605662cc72bf4eedd9493b95fb2090ad3e012f07f8e\"], \"resolved_image_sha256\": [\"e1385136325ab52bf4f86baf046c20a44fd5c1daa0ac17bbacc5c025d4ac8863\", \"dd7e7f9008756a8351902605662cc72bf4eedd9493b95fb2090ad3e012f07f8e\"], \"requested_image_sha256\": [\"e1385136325ab52bf4f86baf046c20a44fd5c1daa0ac17bbacc5c025d4ac8863\", \"dd7e7f9008756a8351902605662cc72bf4eedd9493b95fb2090ad3e012f07f8e\"], \"sent_source_image_refs\": [], \"expected_source_image_refs\": [\"3d714307ded0480caf4c2bf1dfdec114\", \"31b22830c55e4e279090fd9db4c88074\"], \"resolved_source_image_refs\": [\"3d714307ded0480caf4c2bf1dfdec114\", \"31b22830c55e4e279090fd9db4c88074\"], \"requested_source_image_refs\": [\"3d714307ded0480caf4c2bf1dfdec114\", \"31b22830c55e4e279090fd9db4c88074\"]}}',NULL,NULL,'error',NULL,NULL,424,0,'no','provider_auth','2026-08-11 11:22:58','2026-08-11 11:22:58'),('5be4091a6902494ea4e34c5aae8a7afc','5036a26d91f447678f915a573ea816bd','tenant-qualification','54ffb90c68cc8845d3b3908910b83dbb','request_gate','xray_accuracy','openai/compatible','gemini-3-flash-preview','gemini-3-flash-preview','xray.request_gate.v1','v1','13398ca025182287e820f7bbcc251e2cec601fb4af08f2f57776d82c7b38ce6f','d2908fc3eafdfed91ac43178c1ba67079eca50f0332be9052a383975fba5e88b','xray.request-gate-response.v1','57c350f6d4eebacabbfdcfcca1607df17d009527daac4327a56b7b9c989748c8','en','en','c8fead5764f1c6729137b7d4626c5f5327697ed5f646dc0376bb2ef4e8879eaa','{\"status\": \"failed\", \"request_trace\": {\"attempt\": {\"model\": \"gemini-3-flash-preview\", \"stage\": \"request_gate\", \"attempt\": 0, \"timeout\": false, \"full_sent\": \"unknown\", \"latency_ms\": 480, \"module_key\": \"xray_accuracy\", \"prompt_key\": \"xray.request_gate.v1\", \"error_class\": \"provider_auth\", \"image_count\": 2, \"provider_key\": \"openai/compatible\", \"connection_id\": \"configured-real-provider-01\", \"fallback_used\": \"no\", \"prompt_version\": \"v1\", \"prompt_checksum\": \"13398ca025182287e820f7bbcc251e2cec601fb4af08f2f57776d82c7b38ce6f\", \"rendered_sha256\": \"d2908fc3eafdfed91ac43178c1ba67079eca50f0332be9052a383975fba5e88b\", \"stage_attempt_id\": \"95b80c1babca436d8f58b261e697dc67\", \"provider_evidence\": {}, \"provider_attempt_id\": \"54ffb90c68cc8845d3b3908910b83dbb\", \"hard_timeout_seconds\": 8.0, \"image_ordered_sha256\": \"c8fead5764f1c6729137b7d4626c5f5327697ed5f646dc0376bb2ef4e8879eaa\", \"grace_timeout_seconds\": 2.0}}, \"coverage_evidence\": {\"coverage_status\": \"unknown\", \"sent_image_sha256\": [], \"image_ordered_sha256\": \"c8fead5764f1c6729137b7d4626c5f5327697ed5f646dc0376bb2ef4e8879eaa\", \"expected_image_sha256\": [\"e1385136325ab52bf4f86baf046c20a44fd5c1daa0ac17bbacc5c025d4ac8863\", \"dd7e7f9008756a8351902605662cc72bf4eedd9493b95fb2090ad3e012f07f8e\"], \"resolved_image_sha256\": [\"e1385136325ab52bf4f86baf046c20a44fd5c1daa0ac17bbacc5c025d4ac8863\", \"dd7e7f9008756a8351902605662cc72bf4eedd9493b95fb2090ad3e012f07f8e\"], \"requested_image_sha256\": [\"e1385136325ab52bf4f86baf046c20a44fd5c1daa0ac17bbacc5c025d4ac8863\", \"dd7e7f9008756a8351902605662cc72bf4eedd9493b95fb2090ad3e012f07f8e\"], \"sent_source_image_refs\": [], \"expected_source_image_refs\": [\"e9530fe3e4bd4ddc9cbcf54acd1cdf60\", \"7a095c11443d45a893894c68ac7172db\"], \"resolved_source_image_refs\": [\"e9530fe3e4bd4ddc9cbcf54acd1cdf60\", \"7a095c11443d45a893894c68ac7172db\"], \"requested_source_image_refs\": [\"e9530fe3e4bd4ddc9cbcf54acd1cdf60\", \"7a095c11443d45a893894c68ac7172db\"]}}',NULL,NULL,'error',NULL,NULL,480,0,'no','provider_auth','2026-08-11 11:19:26','2026-08-11 11:19:26'),('63cbccb202c34257a11059ea114f57d7','5036a26d91f447678f915a573ea816bd','tenant-qualification','26ba2f7c019436936814ee23193757c2','request_gate','xray_accuracy','openai/compatible','gemini-3-flash-preview','gemini-3-flash-preview','xray.request_gate.v1','v1','13398ca025182287e820f7bbcc251e2cec601fb4af08f2f57776d82c7b38ce6f','d2908fc3eafdfed91ac43178c1ba67079eca50f0332be9052a383975fba5e88b','xray.request-gate-response.v1','57c350f6d4eebacabbfdcfcca1607df17d009527daac4327a56b7b9c989748c8','en','en','c8fead5764f1c6729137b7d4626c5f5327697ed5f646dc0376bb2ef4e8879eaa','{\"status\": \"failed\", \"request_trace\": {\"attempt\": {\"model\": \"gemini-3-flash-preview\", \"stage\": \"request_gate\", \"attempt\": 1, \"timeout\": false, \"full_sent\": \"unknown\", \"latency_ms\": 813, \"module_key\": \"xray_accuracy\", \"prompt_key\": \"xray.request_gate.v1\", \"error_class\": \"provider_auth\", \"image_count\": 2, \"provider_key\": \"openai/compatible\", \"connection_id\": \"configured-real-provider-02\", \"fallback_used\": \"yes\", \"prompt_version\": \"v1\", \"prompt_checksum\": \"13398ca025182287e820f7bbcc251e2cec601fb4af08f2f57776d82c7b38ce6f\", \"rendered_sha256\": \"d2908fc3eafdfed91ac43178c1ba67079eca50f0332be9052a383975fba5e88b\", \"stage_attempt_id\": \"95b80c1babca436d8f58b261e697dc67\", \"provider_evidence\": {}, \"provider_attempt_id\": \"26ba2f7c019436936814ee23193757c2\", \"hard_timeout_seconds\": 8.0, \"image_ordered_sha256\": \"c8fead5764f1c6729137b7d4626c5f5327697ed5f646dc0376bb2ef4e8879eaa\", \"grace_timeout_seconds\": 2.0}}, \"coverage_evidence\": {\"coverage_status\": \"unknown\", \"sent_image_sha256\": [], \"image_ordered_sha256\": \"c8fead5764f1c6729137b7d4626c5f5327697ed5f646dc0376bb2ef4e8879eaa\", \"expected_image_sha256\": [\"e1385136325ab52bf4f86baf046c20a44fd5c1daa0ac17bbacc5c025d4ac8863\", \"dd7e7f9008756a8351902605662cc72bf4eedd9493b95fb2090ad3e012f07f8e\"], \"resolved_image_sha256\": [\"e1385136325ab52bf4f86baf046c20a44fd5c1daa0ac17bbacc5c025d4ac8863\", \"dd7e7f9008756a8351902605662cc72bf4eedd9493b95fb2090ad3e012f07f8e\"], \"requested_image_sha256\": [\"e1385136325ab52bf4f86baf046c20a44fd5c1daa0ac17bbacc5c025d4ac8863\", \"dd7e7f9008756a8351902605662cc72bf4eedd9493b95fb2090ad3e012f07f8e\"], \"sent_source_image_refs\": [], \"expected_source_image_refs\": [\"e9530fe3e4bd4ddc9cbcf54acd1cdf60\", \"7a095c11443d45a893894c68ac7172db\"], \"resolved_source_image_refs\": [\"e9530fe3e4bd4ddc9cbcf54acd1cdf60\", \"7a095c11443d45a893894c68ac7172db\"], \"requested_source_image_refs\": [\"e9530fe3e4bd4ddc9cbcf54acd1cdf60\", \"7a095c11443d45a893894c68ac7172db\"]}}',NULL,NULL,'error',NULL,NULL,813,1,'yes','provider_auth','2026-08-11 11:19:26','2026-08-11 11:19:26'),('a07a02ec4b2b4ee69283dc4e7d7d67f1','5036a26d91f447678f915a573ea816bd','tenant-qualification','518fad58fb89f98363cc33e00ef5d0e7','request_gate','xray_accuracy','openai/compatible','gemini-3-flash-preview','gemini-3-flash-preview','xray.request_gate.v1','v1','13398ca025182287e820f7bbcc251e2cec601fb4af08f2f57776d82c7b38ce6f','d2908fc3eafdfed91ac43178c1ba67079eca50f0332be9052a383975fba5e88b','xray.request-gate-response.v1','57c350f6d4eebacabbfdcfcca1607df17d009527daac4327a56b7b9c989748c8','en','en','c8fead5764f1c6729137b7d4626c5f5327697ed5f646dc0376bb2ef4e8879eaa','{\"status\": \"failed\", \"request_trace\": {\"attempt\": {\"model\": \"gemini-3-flash-preview\", \"stage\": \"request_gate\", \"attempt\": 0, \"timeout\": false, \"full_sent\": \"unknown\", \"latency_ms\": 882, \"module_key\": \"xray_accuracy\", \"prompt_key\": \"xray.request_gate.v1\", \"error_class\": \"provider_auth\", \"image_count\": 2, \"provider_key\": \"openai/compatible\", \"connection_id\": \"configured-real-provider-01\", \"fallback_used\": \"no\", \"prompt_version\": \"v1\", \"prompt_checksum\": \"13398ca025182287e820f7bbcc251e2cec601fb4af08f2f57776d82c7b38ce6f\", \"rendered_sha256\": \"d2908fc3eafdfed91ac43178c1ba67079eca50f0332be9052a383975fba5e88b\", \"stage_attempt_id\": \"95b80c1babca436d8f58b261e697dc67\", \"provider_evidence\": {}, \"provider_attempt_id\": \"518fad58fb89f98363cc33e00ef5d0e7\", \"hard_timeout_seconds\": 8.0, \"image_ordered_sha256\": \"c8fead5764f1c6729137b7d4626c5f5327697ed5f646dc0376bb2ef4e8879eaa\", \"grace_timeout_seconds\": 2.0}}, \"coverage_evidence\": {\"coverage_status\": \"unknown\", \"sent_image_sha256\": [], \"image_ordered_sha256\": \"c8fead5764f1c6729137b7d4626c5f5327697ed5f646dc0376bb2ef4e8879eaa\", \"expected_image_sha256\": [\"e1385136325ab52bf4f86baf046c20a44fd5c1daa0ac17bbacc5c025d4ac8863\", \"dd7e7f9008756a8351902605662cc72bf4eedd9493b95fb2090ad3e012f07f8e\"], \"resolved_image_sha256\": [\"e1385136325ab52bf4f86baf046c20a44fd5c1daa0ac17bbacc5c025d4ac8863\", \"dd7e7f9008756a8351902605662cc72bf4eedd9493b95fb2090ad3e012f07f8e\"], \"requested_image_sha256\": [\"e1385136325ab52bf4f86baf046c20a44fd5c1daa0ac17bbacc5c025d4ac8863\", \"dd7e7f9008756a8351902605662cc72bf4eedd9493b95fb2090ad3e012f07f8e\"], \"sent_source_image_refs\": [], \"expected_source_image_refs\": [\"e9530fe3e4bd4ddc9cbcf54acd1cdf60\", \"7a095c11443d45a893894c68ac7172db\"], \"resolved_source_image_refs\": [\"e9530fe3e4bd4ddc9cbcf54acd1cdf60\", \"7a095c11443d45a893894c68ac7172db\"], \"requested_source_image_refs\": [\"e9530fe3e4bd4ddc9cbcf54acd1cdf60\", \"7a095c11443d45a893894c68ac7172db\"]}}',NULL,NULL,'error',NULL,NULL,882,0,'no','provider_auth','2026-08-11 11:19:23','2026-08-11 11:19:23'),('af1009f4deb4469ba288c356c9391144','68b6258e5f794cea85260a9abc0be482','tenant-schema-recheck','bcc8fa6f02ae2fc276642da605481b05','request_gate','xray_accuracy','stub/replay','xray-engineering-stub.v1','xray-engineering-stub.v1','xray.request_gate.v1','v1','ac59dd389399af1ebe9c41386598321fde222e21e9808d7190dd3fa7f8cd798f','6ff0f545b4fe9db3c8276baf21f49981dac7f85b1fca9b963c923151b519e85c','xray.request-gate-response.v1','57c350f6d4eebacabbfdcfcca1607df17d009527daac4327a56b7b9c989748c8','zh','en',NULL,'{\"status\": \"confirmed\", \"actual_model\": \"xray-engineering-stub.v1\", \"connection_id\": \"stub-default\", \"request_trace\": {\"attempts\": [{\"model\": \"xray-engineering-stub.v1\", \"stage\": \"request_gate\", \"attempt\": 0, \"timeout\": false, \"full_sent\": \"not_applicable\", \"latency_ms\": 0, \"module_key\": \"xray_accuracy\", \"prompt_key\": \"xray.request_gate.v1\", \"prompt_sha\": \"ac59dd389399af1ebe9c41386598321fde222e21e9808d7190dd3fa7f8cd798f\", \"error_class\": null, \"image_count\": 0, \"provider_key\": \"stub/replay\", \"rendered_sha\": \"6ff0f545b4fe9db3c8276baf21f49981dac7f85b1fca9b963c923151b519e85c\", \"connection_id\": \"stub-default\", \"prompt_version\": \"v1\", \"prompt_checksum\": \"ac59dd389399af1ebe9c41386598321fde222e21e9808d7190dd3fa7f8cd798f\", \"stage_attempt_id\": \"f15d01ebacde4be9a9fb744f425aeaf5\", \"provider_attempt_id\": \"bcc8fa6f02ae2fc276642da605481b05\", \"hard_timeout_seconds\": 30.0, \"image_ordered_sha256\": null, \"grace_timeout_seconds\": 2.0}], \"retry_index\": 0, \"connection_id\": \"stub-default\", \"fallback_used\": \"no\", \"provider_attempt_id\": \"bcc8fa6f02ae2fc276642da605481b05\"}, \"image_receipts\": [], \"provider_request_id\": \"stub-d198fe3e69c61cc9f945a133a9805416\", \"image_count_received\": 0, \"receipt_capability_version\": \"stub-receipt.v1\"}','bda8df26e84c33da71cd0ef359dea43c13a1c19a2cf4aebca22d66121ec5feea','bda8df26e84c33da71cd0ef359dea43c13a1c19a2cf4aebca22d66121ec5feea','stop',NULL,NULL,0,0,'no',NULL,'2026-08-10 13:09:04','2026-08-10 13:09:04'),('c10d5a77a4514dd9910db2403b18634e','16e2e68e3cb7491aba284e5087a43655','schema-smoke-tenant','b0b24726ca92c828b4a4cbcf5c02962d','request_gate','xray_accuracy','stub/replay','xray-engineering-stub.v1','xray-engineering-stub.v1','xray.request_gate.v1','v1','ac59dd389399af1ebe9c41386598321fde222e21e9808d7190dd3fa7f8cd798f','f2775c5b0769eaa7b700eb84d36fcbbde5632d1a7f72d213df4aa4b6b54acdfa','xray.request-gate-response.v1','57c350f6d4eebacabbfdcfcca1607df17d009527daac4327a56b7b9c989748c8','zh','en',NULL,'{\"status\": \"confirmed\", \"actual_model\": \"xray-engineering-stub.v1\", \"connection_id\": \"stub-default\", \"request_trace\": {\"attempts\": [{\"model\": \"xray-engineering-stub.v1\", \"stage\": \"request_gate\", \"attempt\": 0, \"timeout\": false, \"full_sent\": \"not_applicable\", \"latency_ms\": 0, \"module_key\": \"xray_accuracy\", \"prompt_key\": \"xray.request_gate.v1\", \"prompt_sha\": \"ac59dd389399af1ebe9c41386598321fde222e21e9808d7190dd3fa7f8cd798f\", \"error_class\": null, \"image_count\": 0, \"provider_key\": \"stub/replay\", \"rendered_sha\": \"f2775c5b0769eaa7b700eb84d36fcbbde5632d1a7f72d213df4aa4b6b54acdfa\", \"connection_id\": \"stub-default\", \"prompt_version\": \"v1\", \"prompt_checksum\": \"ac59dd389399af1ebe9c41386598321fde222e21e9808d7190dd3fa7f8cd798f\", \"stage_attempt_id\": \"fc68e85e39f1477c97eaf8b0637336f3\", \"provider_attempt_id\": \"b0b24726ca92c828b4a4cbcf5c02962d\", \"hard_timeout_seconds\": 30.0, \"image_ordered_sha256\": null, \"grace_timeout_seconds\": 2.0}], \"retry_index\": 0, \"connection_id\": \"stub-default\", \"fallback_used\": \"no\", \"provider_attempt_id\": \"b0b24726ca92c828b4a4cbcf5c02962d\"}, \"image_receipts\": [], \"provider_request_id\": \"stub-6b6e066b55d8d136736d720dfcbe8e02\", \"image_count_received\": 0, \"receipt_capability_version\": \"stub-receipt.v1\"}','bda8df26e84c33da71cd0ef359dea43c13a1c19a2cf4aebca22d66121ec5feea','bda8df26e84c33da71cd0ef359dea43c13a1c19a2cf4aebca22d66121ec5feea','stop',NULL,NULL,0,0,'no',NULL,'2026-08-10 12:40:45','2026-08-10 12:40:45');
/*!40000 ALTER TABLE `xray_accuracy_model_call` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `xray_accuracy_outbox`
--

DROP TABLE IF EXISTS `xray_accuracy_outbox`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `xray_accuracy_outbox` (
  `id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(64)：Outbox event 唯一标识',
  `run_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(64)：所属 Run opaque 标识，不声明 foreign key',
  `tenant_id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(128)：租户标识，发布前必须校验',
  `task_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(64)：异步任务幂等标识',
  `stage_key` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(64)：阶段节点白名单名称',
  `release_fingerprint` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(128)：发布指纹，不携带医学结论',
  `expected_version` int NOT NULL COMMENT 'INT：消费者执行 CAS 的预期版本',
  `trace_namespace` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(128)：跨进程 trace namespace',
  `message_json` json NOT NULL COMMENT 'JSON：仅允许白名单消息字段，禁止 prompt/image/truth/output',
  `message_payload_hash` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'CHAR(64)：白名单消息规范化 SHA256，用于 Broker 对账',
  `message_whitelist_version` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(32)：跨进程消息字段白名单版本',
  `event_type` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(64)：事件类型 execute/reconcile/review/delivery；取消由 stage_key 表示',
  `publish_status` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(32)：发布状态 pending/publishing/published/retry/dead_letter',
  `relay_owner_id` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'VARCHAR(128)：Outbox relay lease 所有者，可为空',
  `relay_lease_expires_at` datetime DEFAULT NULL COMMENT 'TIMESTAMP：Outbox relay lease 到期时间（UTC）',
  `attempt_count` int NOT NULL COMMENT 'INT：relay 发布尝试次数',
  `next_retry_at` datetime DEFAULT NULL COMMENT 'TIMESTAMP：下次发布重试时间（UTC）',
  `published_at` datetime DEFAULT NULL COMMENT 'TIMESTAMP：发布确认时间（UTC）',
  `last_error` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'VARCHAR(255)：脱敏技术错误摘要，禁止密钥/URL/原图',
  `created_at` datetime NOT NULL DEFAULT (now()) COMMENT 'TIMESTAMP：记录创建时间（UTC），用于不可变审计',
  `updated_at` datetime NOT NULL DEFAULT (now()) COMMENT 'TIMESTAMP：记录更新时间（UTC），仅技术状态可更新',
  `consumer_status` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'pending' COMMENT 'VARCHAR(32)：消费者状态 pending/running/completed/retry_wait/dead_letter/cancelled',
  `consumer_owner_id` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'VARCHAR(128)：Worker consumer lease 所有者，可为空',
  `consumer_lease_expires_at` datetime DEFAULT NULL COMMENT 'TIMESTAMP：Worker consumer lease 到期时间（UTC）',
  `consumer_attempt_count` int NOT NULL DEFAULT '0' COMMENT 'INT：消费者执行尝试次数，与 relay 发布次数分离',
  `consumer_started_at` datetime DEFAULT NULL COMMENT 'TIMESTAMP：消费者开始执行时间（UTC）',
  `consumer_finished_at` datetime DEFAULT NULL COMMENT 'TIMESTAMP：消费者完成时间（UTC）',
  `consumer_next_retry_at` datetime DEFAULT NULL COMMENT 'TIMESTAMP：消费者下次重试时间（UTC）',
  `consumer_last_error` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'VARCHAR(255)：脱敏消费者错误，不含密钥/URL/原图',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_xray_outbox_tenant_run_task` (`tenant_id`,`run_id`,`task_id`),
  KEY `ix_xray_outbox_tenant_publish_retry` (`tenant_id`,`publish_status`,`next_retry_at`),
  KEY `ix_xray_outbox_run` (`run_id`),
  KEY `ix_xray_outbox_publish_retry` (`publish_status`,`next_retry_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `xray_accuracy_outbox`
--

LOCK TABLES `xray_accuracy_outbox` WRITE;
/*!40000 ALTER TABLE `xray_accuracy_outbox` DISABLE KEYS */;
INSERT INTO `xray_accuracy_outbox` VALUES ('0c982ea705a340e4836e4bc446ff3305','2f1e56b85c7e48a68b71aabd3e918d5e','tenant-qualification','5a6d87e4a67a462aadcfc9008c2b691d','request_gate','cbc14413743f80a97e4699c0c50e4820',0,'xray.v2:2f1e56b85c7e48a68b71aabd3e918d5e','{\"run_id\": \"2f1e56b85c7e48a68b71aabd3e918d5e\", \"task_id\": \"5a6d87e4a67a462aadcfc9008c2b691d\", \"stage_key\": \"request_gate\", \"trace_namespace\": \"xray.v2:2f1e56b85c7e48a68b71aabd3e918d5e\", \"expected_version\": 0, \"release_fingerprint\": \"cbc14413743f80a97e4699c0c50e4820\"}','dceb86174d1968e29fcf2eaf0449f8a9b082f52de073a4ea33d3487d759bdcb3','xray-message.v1','execute','published',NULL,NULL,0,NULL,'2026-08-11 03:22:57',NULL,'2026-08-11 11:22:57','2026-08-11 11:22:58','dead_letter',NULL,NULL,1,'2026-08-11 03:22:57','2026-08-11 03:22:58',NULL,'provider_auth'),('1d7d71d96a204b4e97d9baa8574d347b','68b6258e5f794cea85260a9abc0be482','tenant-schema-recheck','f15d01ebacde4be9a9fb744f425aeaf5','request_gate','4384de96a91b60bc8d6f4c1d36518305',0,'xray.v2:68b6258e5f794cea85260a9abc0be482','{\"run_id\": \"68b6258e5f794cea85260a9abc0be482\", \"task_id\": \"f15d01ebacde4be9a9fb744f425aeaf5\", \"stage_key\": \"request_gate\", \"trace_namespace\": \"xray.v2:68b6258e5f794cea85260a9abc0be482\", \"expected_version\": 0, \"release_fingerprint\": \"4384de96a91b60bc8d6f4c1d36518305\"}','98700eee5a5e9506933eaad9eb40d522256fb02dfd0293d953eb96117ee1454c','xray-message.v1','execute','published',NULL,NULL,0,NULL,'2026-08-10 05:09:04',NULL,'2026-08-10 13:09:04','2026-08-10 13:09:04','pending',NULL,NULL,0,NULL,NULL,NULL,NULL),('38cbefa1912840fd837a4032a4dd518d','5036a26d91f447678f915a573ea816bd','tenant-qualification','95b80c1babca436d8f58b261e697dc67','request_gate','cbc14413743f80a97e4699c0c50e4820',0,'xray.v2:5036a26d91f447678f915a573ea816bd','{\"run_id\": \"5036a26d91f447678f915a573ea816bd\", \"task_id\": \"95b80c1babca436d8f58b261e697dc67\", \"stage_key\": \"request_gate\", \"trace_namespace\": \"xray.v2:5036a26d91f447678f915a573ea816bd\", \"expected_version\": 0, \"release_fingerprint\": \"cbc14413743f80a97e4699c0c50e4820\"}','66d3b7339270418ec5b5b50afd40fab1325a4c6f1bef8c8974c43d8434f31f8f','xray-message.v1','execute','published',NULL,NULL,0,NULL,'2026-08-11 03:19:21',NULL,'2026-08-11 11:19:20','2026-08-11 11:19:26','dead_letter',NULL,NULL,2,'2026-08-11 03:19:24','2026-08-11 03:19:26',NULL,'provider_auth'),('5e27877d1a484b93863f7b1412375fd5','c199b1bb84e1487393df8af188c76a1e','tenant-qualification','31323ddec9c54257a5de4454bd9c4a54','request_gate','90e9abb856f4fef6042ea15dbbfcf2d6',0,'xray.v2:c199b1bb84e1487393df8af188c76a1e','{\"run_id\": \"c199b1bb84e1487393df8af188c76a1e\", \"task_id\": \"31323ddec9c54257a5de4454bd9c4a54\", \"stage_key\": \"request_gate\", \"trace_namespace\": \"xray.v2:c199b1bb84e1487393df8af188c76a1e\", \"expected_version\": 0, \"release_fingerprint\": \"90e9abb856f4fef6042ea15dbbfcf2d6\"}','016d0a26fb2dd709851db9c0b9138853c12a743ba2445462b68c2081254fde71','xray-message.v1','execute','published',NULL,NULL,0,NULL,'2026-08-11 03:18:35',NULL,'2026-08-11 11:18:35','2026-08-11 11:18:35','completed',NULL,NULL,1,'2026-08-11 03:18:35','2026-08-11 03:18:35',NULL,NULL),('6f121d1f07204f8a9c862ec046698a55','ce7e9a7f363f48499e512bc03c6b3712','tenant-qualification','de0fb342c48a43a8b21de8c0527d80f8','request_gate','cbc14413743f80a97e4699c0c50e4820',0,'xray.v2:ce7e9a7f363f48499e512bc03c6b3712','{\"run_id\": \"ce7e9a7f363f48499e512bc03c6b3712\", \"task_id\": \"de0fb342c48a43a8b21de8c0527d80f8\", \"stage_key\": \"request_gate\", \"trace_namespace\": \"xray.v2:ce7e9a7f363f48499e512bc03c6b3712\", \"expected_version\": 0, \"release_fingerprint\": \"cbc14413743f80a97e4699c0c50e4820\"}','fd7d231913dacab145d9eb6dc5ed2bb17c1439df2107d9a7ad310c30110942cb','xray-message.v1','execute','pending',NULL,NULL,0,NULL,NULL,NULL,'2026-08-11 11:17:29','2026-08-11 11:17:29','pending',NULL,NULL,0,NULL,NULL,NULL,NULL),('7b609bd2ca124d69985ab2f88d18b537','16e2e68e3cb7491aba284e5087a43655','schema-smoke-tenant','fc68e85e39f1477c97eaf8b0637336f3','request_gate','4384de96a91b60bc8d6f4c1d36518305',0,'xray.v2:16e2e68e3cb7491aba284e5087a43655','{\"run_id\": \"16e2e68e3cb7491aba284e5087a43655\", \"task_id\": \"fc68e85e39f1477c97eaf8b0637336f3\", \"stage_key\": \"request_gate\", \"trace_namespace\": \"xray.v2:16e2e68e3cb7491aba284e5087a43655\", \"expected_version\": 0, \"release_fingerprint\": \"4384de96a91b60bc8d6f4c1d36518305\"}','2650d52734a5a03130e53b1fc8ac87d373aa5e53cf119aa42787bf9f8dc99426','xray-message.v1','execute','published',NULL,NULL,0,NULL,'2026-08-10 04:40:46',NULL,'2026-08-10 12:40:45','2026-08-10 12:40:45','pending',NULL,NULL,0,NULL,NULL,NULL,NULL),('b8298ad7f82b4fcf81e025e547857548','e850b4b444b244d9a11f1f0e03be78d4','tenant-qualification','370d456185754eb0b71007219d315141','request_gate','90e9abb856f4fef6042ea15dbbfcf2d6',0,'xray.v2:e850b4b444b244d9a11f1f0e03be78d4','{\"run_id\": \"e850b4b444b244d9a11f1f0e03be78d4\", \"task_id\": \"370d456185754eb0b71007219d315141\", \"stage_key\": \"request_gate\", \"trace_namespace\": \"xray.v2:e850b4b444b244d9a11f1f0e03be78d4\", \"expected_version\": 0, \"release_fingerprint\": \"90e9abb856f4fef6042ea15dbbfcf2d6\"}','91f6e839866ae58acd095d6645cd2af55d3210ae3089df344b3c2b3f42bd2a11','xray-message.v1','execute','published',NULL,NULL,0,NULL,'2026-08-11 03:17:48',NULL,'2026-08-11 11:17:48','2026-08-11 11:17:48','completed',NULL,NULL,1,'2026-08-11 03:17:48','2026-08-11 03:17:49',NULL,NULL),('d0ff5a1326d34c8a923602780c883bbc','071bed59e733450bb4752fc3ee3ffd02','tenant-qualification','395ca9ed57934d9381103069fbb53d9c','request_gate','90e9abb856f4fef6042ea15dbbfcf2d6',0,'xray.v2:071bed59e733450bb4752fc3ee3ffd02','{\"run_id\": \"071bed59e733450bb4752fc3ee3ffd02\", \"task_id\": \"395ca9ed57934d9381103069fbb53d9c\", \"stage_key\": \"request_gate\", \"trace_namespace\": \"xray.v2:071bed59e733450bb4752fc3ee3ffd02\", \"expected_version\": 0, \"release_fingerprint\": \"90e9abb856f4fef6042ea15dbbfcf2d6\"}','8ec367972e110c26d875e3e06a84dd0fc8b68af85a68fbb5fbd7eb3cec287bd0','xray-message.v1','execute','published',NULL,NULL,0,NULL,'2026-08-11 03:15:25',NULL,'2026-08-11 11:15:25','2026-08-11 11:15:26','completed',NULL,NULL,1,'2026-08-11 03:15:25','2026-08-11 03:15:26',NULL,NULL),('d6706962c07b48a4834b2f55e101a126','f3e49dc1172a485a8192a201c9c02c35','tenant-qualification','b30b1e5b326d48c7a03218ffeb8a4ef2','request_gate','90e9abb856f4fef6042ea15dbbfcf2d6',0,'xray.v2:f3e49dc1172a485a8192a201c9c02c35','{\"run_id\": \"f3e49dc1172a485a8192a201c9c02c35\", \"task_id\": \"b30b1e5b326d48c7a03218ffeb8a4ef2\", \"stage_key\": \"request_gate\", \"trace_namespace\": \"xray.v2:f3e49dc1172a485a8192a201c9c02c35\", \"expected_version\": 0, \"release_fingerprint\": \"90e9abb856f4fef6042ea15dbbfcf2d6\"}','f0513b4d94e27138adb3b49ff5fad4bf83ee739a18866e22ffe3f20f0eb40aeb','xray-message.v1','execute','published',NULL,NULL,0,NULL,'2026-08-11 03:22:57',NULL,'2026-08-11 11:22:57','2026-08-11 11:22:57','completed',NULL,NULL,1,'2026-08-11 03:22:57','2026-08-11 03:22:57',NULL,NULL),('d8502b4f412d48dfa243c017d685758a','f38565fcab284c4bb26e424c09870f0f','tenant-qualification','4efb9f07635c404a8fee1813fc2f6952','request_gate','90e9abb856f4fef6042ea15dbbfcf2d6',0,'xray.v2:f38565fcab284c4bb26e424c09870f0f','{\"run_id\": \"f38565fcab284c4bb26e424c09870f0f\", \"task_id\": \"4efb9f07635c404a8fee1813fc2f6952\", \"stage_key\": \"request_gate\", \"trace_namespace\": \"xray.v2:f38565fcab284c4bb26e424c09870f0f\", \"expected_version\": 0, \"release_fingerprint\": \"90e9abb856f4fef6042ea15dbbfcf2d6\"}','1c96afeb702126160b1e4035885ad18b11a35e572af63d578247f37a32b2cef5','xray-message.v1','execute','published',NULL,NULL,0,NULL,'2026-08-11 03:19:20',NULL,'2026-08-11 11:19:20','2026-08-11 11:19:20','completed',NULL,NULL,1,'2026-08-11 03:19:20','2026-08-11 03:19:21',NULL,NULL);
/*!40000 ALTER TABLE `xray_accuracy_outbox` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `xray_accuracy_request_snapshot`
--

DROP TABLE IF EXISTS `xray_accuracy_request_snapshot`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `xray_accuracy_request_snapshot` (
  `id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(64)：RequestSnapshot 唯一标识',
  `run_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(64)：所属 Run opaque 标识，不声明 foreign key',
  `tenant_id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(128)：租户标识，查询必须与 JWT tenant 一致',
  `study_revision` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(128)：不可变 Study revision opaque 标识，不含 truth',
  `manifest_json` json NOT NULL COMMENT 'JSON：不可变 expected image manifest，不含 bytes/secret',
  `safe_metadata_json` json DEFAULT NULL COMMENT 'JSON：允许的安全元数据，不含历史输出/truth/OCR/EXIF',
  `immutable_at` datetime DEFAULT NULL COMMENT 'TIMESTAMP：快照冻结时间（UTC）',
  `created_at` datetime NOT NULL DEFAULT (now()) COMMENT 'TIMESTAMP：记录创建时间（UTC），用于不可变审计',
  `updated_at` datetime NOT NULL DEFAULT (now()) COMMENT 'TIMESTAMP：记录更新时间（UTC），仅技术状态可更新',
  `session_id` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'VARCHAR(64)：所属 Session opaque 标识，不声明 foreign key',
  `study_id` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'VARCHAR(128)：所属 Study opaque 标识，不声明 foreign key',
  `requested_operation` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'diagnose' COMMENT 'VARCHAR(32)：快照对应的 prepare_study/diagnose 操作',
  PRIMARY KEY (`id`),
  KEY `ix_xray_snapshot_tenant_run` (`tenant_id`,`run_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `xray_accuracy_request_snapshot`
--

LOCK TABLES `xray_accuracy_request_snapshot` WRITE;
/*!40000 ALTER TABLE `xray_accuracy_request_snapshot` DISABLE KEYS */;
INSERT INTO `xray_accuracy_request_snapshot` VALUES ('009a2c4c497e4c16b1e5999825def4aa','68b6258e5f794cea85260a9abc0be482','tenant-schema-recheck','study-recheck-v1','[{\"mime_type\": \"image/jpeg\", \"source_index\": 0, \"source_image_ref\": \"opaque-recheck-0\"}]','{\"source\": \"schema-recheck\"}','2026-08-10 05:09:04','2026-08-10 13:09:04','2026-08-10 13:09:04',NULL,NULL,'diagnose'),('255bf0c13893415c9b860cd4e1e55745','f38565fcab284c4bb26e424c09870f0f','tenant-qualification','5dd1c37c4a03b16187d03f3aacab79bb','[{\"mime_type\": null, \"source_index\": 0, \"source_image_ref\": \"e9530fe3e4bd4ddc9cbcf54acd1cdf60\"}, {\"mime_type\": null, \"source_index\": 1, \"source_image_ref\": \"7a095c11443d45a893894c68ac7172db\"}]','null','2026-08-11 03:19:20','2026-08-11 11:19:20','2026-08-11 11:19:20','f004b4b097594defa289f1c0024c368a','qualification-study:0b5149fd055548519a9689b91a1477df','prepare_study'),('4a0919a9d00a4378b262f43465bbf0e7','071bed59e733450bb4752fc3ee3ffd02','tenant-qualification','de755a8134f92bb19d3e4d0d05408bb8','[{\"mime_type\": null, \"source_index\": 0, \"source_image_ref\": \"3d08c3a29db44f508e44bbe2b8b061a2\"}, {\"mime_type\": null, \"source_index\": 1, \"source_image_ref\": \"8207d3c466584f4e8b5aa958ae45c267\"}]','null','2026-08-11 03:15:25','2026-08-11 11:15:25','2026-08-11 11:15:25','593f5fe0e0254cce999ac6148f6f9f93','qualification-study:c1b34ab6465d4feab3c01e4653317d23','prepare_study'),('5e39ab645b93414dafd387540f3f3ca7','5036a26d91f447678f915a573ea816bd','tenant-qualification','5dd1c37c4a03b16187d03f3aacab79bb','[{\"mime_type\": null, \"source_index\": 0, \"source_image_ref\": \"e9530fe3e4bd4ddc9cbcf54acd1cdf60\"}, {\"mime_type\": null, \"source_index\": 1, \"source_image_ref\": \"7a095c11443d45a893894c68ac7172db\"}]','null','2026-08-11 03:19:21','2026-08-11 11:19:20','2026-08-11 11:19:20','f004b4b097594defa289f1c0024c368a','qualification-study:0b5149fd055548519a9689b91a1477df','diagnose'),('7d327b447efa418bad8ce5ef725ffcec','f3e49dc1172a485a8192a201c9c02c35','tenant-qualification','89a37bf064279907c0f5c2b4c00ba4c5','[{\"mime_type\": null, \"source_index\": 0, \"source_image_ref\": \"3d714307ded0480caf4c2bf1dfdec114\"}, {\"mime_type\": null, \"source_index\": 1, \"source_image_ref\": \"31b22830c55e4e279090fd9db4c88074\"}]','null','2026-08-11 03:22:57','2026-08-11 11:22:57','2026-08-11 11:22:57','e5b71ffc99ed4d0ebfcc9f539184bc05','qualification-study:4f3648dc5e91425fa26a6ed601334bc4','prepare_study'),('96963eb2b9af411f82e6555c4aa5c45b','16e2e68e3cb7491aba284e5087a43655','schema-smoke-tenant','schema-smoke-study-v1','[{\"mime_type\": \"image/png\", \"source_index\": 0, \"source_image_ref\": \"image-smoke-0\"}]','{\"source\": \"schema_smoke\"}','2026-08-10 04:40:46','2026-08-10 12:40:45','2026-08-10 12:40:45',NULL,NULL,'diagnose'),('c8cff0f3177549c58b6b45aab674b41e','e850b4b444b244d9a11f1f0e03be78d4','tenant-qualification','2f6cbe2e2e4be621e8f12f87cd9fb987','[{\"mime_type\": null, \"source_index\": 0, \"source_image_ref\": \"1218e60f43fb42c3b903fb072e65b85e\"}, {\"mime_type\": null, \"source_index\": 1, \"source_image_ref\": \"382da4af838b420e9c04bac1c166a068\"}]','null','2026-08-11 03:17:48','2026-08-11 11:17:48','2026-08-11 11:17:48','c6908ebe329141b487fe7418d09ff644','qualification-study:8ee60f42cd7c4492bf045cdb24dbd1b6','prepare_study'),('e18798a98a2f42cea2624c71ee9f5096','ce7e9a7f363f48499e512bc03c6b3712','tenant-qualification','de755a8134f92bb19d3e4d0d05408bb8','[{\"mime_type\": null, \"source_index\": 0, \"source_image_ref\": \"3d08c3a29db44f508e44bbe2b8b061a2\"}, {\"mime_type\": null, \"source_index\": 1, \"source_image_ref\": \"8207d3c466584f4e8b5aa958ae45c267\"}]','null','2026-08-11 03:17:30','2026-08-11 11:17:29','2026-08-11 11:17:29','593f5fe0e0254cce999ac6148f6f9f93','qualification-study:c1b34ab6465d4feab3c01e4653317d23','diagnose'),('e7ae3b7c7c0d4f32a7b095fc143cdeb0','c199b1bb84e1487393df8af188c76a1e','tenant-qualification','958907665516068286d06f85562cb07e','[{\"mime_type\": null, \"source_index\": 0, \"source_image_ref\": \"1aa51013104e4195a5711c37c6d0e194\"}, {\"mime_type\": null, \"source_index\": 1, \"source_image_ref\": \"5c4a27a4344e4617ab1ea33dfd954d0c\"}]','null','2026-08-11 03:18:35','2026-08-11 11:18:35','2026-08-11 11:18:35','df7343d22b1e4e54b8b4ec44d0973720','qualification-study:d3a7ad36501142fc85b910748c988aa9','prepare_study'),('f1956741aeb047b9a885e853aafc16bb','2f1e56b85c7e48a68b71aabd3e918d5e','tenant-qualification','89a37bf064279907c0f5c2b4c00ba4c5','[{\"mime_type\": null, \"source_index\": 0, \"source_image_ref\": \"3d714307ded0480caf4c2bf1dfdec114\"}, {\"mime_type\": null, \"source_index\": 1, \"source_image_ref\": \"31b22830c55e4e279090fd9db4c88074\"}]','null','2026-08-11 03:22:57','2026-08-11 11:22:57','2026-08-11 11:22:57','e5b71ffc99ed4d0ebfcc9f539184bc05','qualification-study:4f3648dc5e91425fa26a6ed601334bc4','diagnose');
/*!40000 ALTER TABLE `xray_accuracy_request_snapshot` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `xray_accuracy_run`
--

DROP TABLE IF EXISTS `xray_accuracy_run`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `xray_accuracy_run` (
  `id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(64)：Run 唯一标识（opaque）',
  `tenant_id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(128)：租户标识，来自已验证 JWT，不接受请求覆盖',
  `subject_id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(128)：认证主体标识，不承载医学结论',
  `request_id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(128)：客户端幂等请求标识',
  `case_request_id` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'VARCHAR(128)：上游病例请求 opaque 标识，可为空',
  `contract_version` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(64)：API/数据合同版本字符串',
  `payload_sha256` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'CHAR(64)：规范化请求 SHA256，不含 secret/原图 bytes',
  `release_fingerprint` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(128)：validation-only 发布指纹，不代表生产发布',
  `trace_namespace` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(128)：HTTP→Outbox→Worker trace 命名空间',
  `state_version` bigint NOT NULL COMMENT 'BIGINT：Run CAS 状态版本，单调递增',
  `execution_status` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(32)：执行状态 queued/running/completed/failed/cancel_requested/cancelled',
  `execution_mode` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'validation_only' COMMENT 'VARCHAR(32)：执行模式 validation_only/production，单一执行模式事实源',
  `ai_medical_status` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(32)：医学状态 not_produced，零模型阶段禁止写 verdict',
  `delivery_status` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(32)：交付状态 not_published/held/published；执行模式由 validation_only 单独表达',
  `engineering_eligibility` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(32)：工程可评估状态 unknown/clean/failed',
  `completed_at` datetime DEFAULT NULL COMMENT 'TIMESTAMP：技术终态时间（UTC），未终态为空',
  `created_at` datetime NOT NULL DEFAULT (now()) COMMENT 'TIMESTAMP：记录创建时间（UTC），用于不可变审计',
  `updated_at` datetime NOT NULL DEFAULT (now()) COMMENT 'TIMESTAMP：记录更新时间（UTC），仅技术状态可更新',
  `session_id` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'VARCHAR(64)：所属 Session opaque 标识，不声明 foreign key',
  `study_id` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'VARCHAR(128)：所属 Study opaque 标识，不声明 foreign key',
  `requested_operation` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'diagnose' COMMENT 'VARCHAR(32)：运行操作 prepare_study/diagnose/qualification',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_xray_run_tenant_request_contract` (`tenant_id`,`request_id`,`contract_version`),
  KEY `ix_xray_run_tenant_status` (`tenant_id`,`execution_status`),
  KEY `ix_xray_accuracy_run_tenant_id` (`tenant_id`),
  KEY `ix_xray_run_tenant_created` (`tenant_id`,`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `xray_accuracy_run`
--

LOCK TABLES `xray_accuracy_run` WRITE;
/*!40000 ALTER TABLE `xray_accuracy_run` DISABLE KEYS */;
INSERT INTO `xray_accuracy_run` VALUES ('071bed59e733450bb4752fc3ee3ffd02','tenant-qualification','provider-qualification','prepare:qualification-study:c1b34ab6465d4feab3c01e4653317d23',NULL,'xray-study-preparation.v1','747d3c8857a445fd65645d00faafa3fc0bfa3fc434f7afc76a74ac0b6bcbe523','90e9abb856f4fef6042ea15dbbfcf2d6','xray.v2:071bed59e733450bb4752fc3ee3ffd02',1,'completed','validation_only','not_produced','not_published','clean','2026-08-11 03:15:26','2026-08-11 11:15:25','2026-08-11 11:15:26','593f5fe0e0254cce999ac6148f6f9f93','qualification-study:c1b34ab6465d4feab3c01e4653317d23','prepare_study'),('16e2e68e3cb7491aba284e5087a43655','schema-smoke-tenant','schema-smoke-subject','schema-smoke-8db8f1cdc0a3428cb1f47b9608894737','schema-smoke-case','xray-run.v1','2024289534338506454db0d93f5569eb95d7f892685a166f9419ab340eba4736','4384de96a91b60bc8d6f4c1d36518305','xray.v2:16e2e68e3cb7491aba284e5087a43655',1,'completed','validation_only','not_produced','not_published','clean','2026-08-10 04:40:46','2026-08-10 12:40:45','2026-08-10 12:40:45',NULL,NULL,'diagnose'),('2f1e56b85c7e48a68b71aabd3e918d5e','tenant-qualification','provider-qualification','qualification-diagnose:4f3648dc5e91425fa26a6ed601334bc4',NULL,'xray-provider-qualification.v1','414c628f327321ebbaca8c63b668acf7c9660f7e8b795fe73717905d10ae1f63','cbc14413743f80a97e4699c0c50e4820','xray.v2:2f1e56b85c7e48a68b71aabd3e918d5e',0,'queued','validation_only','not_produced','not_published','unknown',NULL,'2026-08-11 11:22:57','2026-08-11 11:22:57','e5b71ffc99ed4d0ebfcc9f539184bc05','qualification-study:4f3648dc5e91425fa26a6ed601334bc4','diagnose'),('5036a26d91f447678f915a573ea816bd','tenant-qualification','provider-qualification','qualification-diagnose:0b5149fd055548519a9689b91a1477df',NULL,'xray-provider-qualification.v1','a96e2f799e8afca218ded60a389dc0421edc2bc00525e5feec52e23b4335090f','cbc14413743f80a97e4699c0c50e4820','xray.v2:5036a26d91f447678f915a573ea816bd',0,'queued','validation_only','not_produced','not_published','unknown',NULL,'2026-08-11 11:19:20','2026-08-11 11:19:20','f004b4b097594defa289f1c0024c368a','qualification-study:0b5149fd055548519a9689b91a1477df','diagnose'),('68b6258e5f794cea85260a9abc0be482','tenant-schema-recheck','subject-recheck','recheck-8979f7856d324c02a55b9c2e889fe0d4',NULL,'xray-run.v1','8a20cab3693be6edf2c2c3774f8b823b4220458bb1cf23483b49d3e8b7a675d1','4384de96a91b60bc8d6f4c1d36518305','xray.v2:68b6258e5f794cea85260a9abc0be482',1,'completed','validation_only','not_produced','not_published','clean','2026-08-10 05:09:04','2026-08-10 13:09:04','2026-08-10 13:09:04',NULL,NULL,'diagnose'),('c199b1bb84e1487393df8af188c76a1e','tenant-qualification','provider-qualification','prepare:qualification-study:d3a7ad36501142fc85b910748c988aa9',NULL,'xray-study-preparation.v1','24abf7af2508bb9b057382ad4ce6bd8d87dd196d167843eef53f362e4b9aa0f2','90e9abb856f4fef6042ea15dbbfcf2d6','xray.v2:c199b1bb84e1487393df8af188c76a1e',1,'completed','validation_only','not_produced','not_published','clean','2026-08-11 03:18:35','2026-08-11 11:18:35','2026-08-11 11:18:35','df7343d22b1e4e54b8b4ec44d0973720','qualification-study:d3a7ad36501142fc85b910748c988aa9','prepare_study'),('ce7e9a7f363f48499e512bc03c6b3712','tenant-qualification','provider-qualification','debug-diagnose:e17bdc85308847839247d3baa1cfa800',NULL,'xray-provider-qualification.v1','870f765cd3127e5a637c10f3a8ef4f1a74dfc3192d88534670fcd339952d2f66','cbc14413743f80a97e4699c0c50e4820','xray.v2:ce7e9a7f363f48499e512bc03c6b3712',0,'queued','validation_only','not_produced','not_published','unknown',NULL,'2026-08-11 11:17:29','2026-08-11 11:17:29','593f5fe0e0254cce999ac6148f6f9f93','qualification-study:c1b34ab6465d4feab3c01e4653317d23','diagnose'),('e850b4b444b244d9a11f1f0e03be78d4','tenant-qualification','provider-qualification','prepare:qualification-study:8ee60f42cd7c4492bf045cdb24dbd1b6',NULL,'xray-study-preparation.v1','ff9a540c09d73126ebfbdea054d526519337c8778fcbf419dead67d654bb7d00','90e9abb856f4fef6042ea15dbbfcf2d6','xray.v2:e850b4b444b244d9a11f1f0e03be78d4',1,'completed','validation_only','not_produced','not_published','clean','2026-08-11 03:17:49','2026-08-11 11:17:48','2026-08-11 11:17:48','c6908ebe329141b487fe7418d09ff644','qualification-study:8ee60f42cd7c4492bf045cdb24dbd1b6','prepare_study'),('f38565fcab284c4bb26e424c09870f0f','tenant-qualification','provider-qualification','prepare:qualification-study:0b5149fd055548519a9689b91a1477df',NULL,'xray-study-preparation.v1','c5336192429a0d22fb58af4754722e88e22284687366fa1d7ff7c186778b01ee','90e9abb856f4fef6042ea15dbbfcf2d6','xray.v2:f38565fcab284c4bb26e424c09870f0f',1,'completed','validation_only','not_produced','not_published','clean','2026-08-11 03:19:21','2026-08-11 11:19:20','2026-08-11 11:19:20','f004b4b097594defa289f1c0024c368a','qualification-study:0b5149fd055548519a9689b91a1477df','prepare_study'),('f3e49dc1172a485a8192a201c9c02c35','tenant-qualification','provider-qualification','prepare:qualification-study:4f3648dc5e91425fa26a6ed601334bc4',NULL,'xray-study-preparation.v1','b208aefb39ead20b2fb6552ba259454289361519e4670f7ce3d91769989813de','90e9abb856f4fef6042ea15dbbfcf2d6','xray.v2:f3e49dc1172a485a8192a201c9c02c35',1,'completed','validation_only','not_produced','not_published','clean','2026-08-11 03:22:57','2026-08-11 11:22:57','2026-08-11 11:22:57','e5b71ffc99ed4d0ebfcc9f539184bc05','qualification-study:4f3648dc5e91425fa26a6ed601334bc4','prepare_study');
/*!40000 ALTER TABLE `xray_accuracy_run` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `xray_accuracy_session`
--

DROP TABLE IF EXISTS `xray_accuracy_session`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `xray_accuracy_session` (
  `id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(64)：Session opaque 标识，不声明 foreign key',
  `tenant_id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(128)：租户标识，来自已验证 JWT',
  `subject_id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(128)：认证主体 opaque 标识',
  `request_id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(128)：Session 创建幂等请求标识',
  `case_request_id` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'VARCHAR(128)：上游病例请求 opaque 标识',
  `module_key` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(64)：业务模块标识，当前固定 xray',
  `session_status` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(32)：Session 状态 open/closed/cancelled',
  `metadata_json` json DEFAULT NULL COMMENT 'JSON：不含 truth/Prompt/原图地址的安全会话元数据',
  `closed_at` datetime DEFAULT NULL COMMENT 'TIMESTAMP：Session 关闭时间（UTC）',
  `created_at` datetime NOT NULL DEFAULT (now()) COMMENT 'TIMESTAMP：记录创建时间（UTC），用于不可变审计',
  `updated_at` datetime NOT NULL DEFAULT (now()) COMMENT 'TIMESTAMP：记录更新时间（UTC），仅技术状态可更新',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_xray_session_tenant_request` (`tenant_id`,`request_id`),
  KEY `ix_xray_session_tenant_created` (`tenant_id`,`created_at`),
  KEY `ix_xray_accuracy_session_tenant_id` (`tenant_id`),
  KEY `ix_xray_session_tenant_status` (`tenant_id`,`session_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `xray_accuracy_session`
--

LOCK TABLES `xray_accuracy_session` WRITE;
/*!40000 ALTER TABLE `xray_accuracy_session` DISABLE KEYS */;
INSERT INTO `xray_accuracy_session` VALUES ('0c7504ea9fa2434a90284448d9390a18','tenant-qualification','provider-qualification','qualification-session:d089bf1f6c964d3bba95b7fed03e55c1',NULL,'xray-provider-qualification','open','{\"qualification\": true}',NULL,'2026-08-11 11:13:10','2026-08-11 11:13:10'),('593f5fe0e0254cce999ac6148f6f9f93','tenant-qualification','provider-qualification','qualification-session:c1b34ab6465d4feab3c01e4653317d23',NULL,'xray-provider-qualification','open','{\"qualification\": true}',NULL,'2026-08-11 11:15:25','2026-08-11 11:15:25'),('c6908ebe329141b487fe7418d09ff644','tenant-qualification','provider-qualification','qualification-session:8ee60f42cd7c4492bf045cdb24dbd1b6',NULL,'xray-provider-qualification','open','{\"qualification\": true}',NULL,'2026-08-11 11:17:48','2026-08-11 11:17:48'),('df7343d22b1e4e54b8b4ec44d0973720','tenant-qualification','provider-qualification','qualification-session:d3a7ad36501142fc85b910748c988aa9',NULL,'xray-provider-qualification','open','{\"qualification\": true}',NULL,'2026-08-11 11:18:35','2026-08-11 11:18:35'),('e5b71ffc99ed4d0ebfcc9f539184bc05','tenant-qualification','provider-qualification','qualification-session:4f3648dc5e91425fa26a6ed601334bc4',NULL,'xray-provider-qualification','open','{\"qualification\": true}',NULL,'2026-08-11 11:22:57','2026-08-11 11:22:57'),('f004b4b097594defa289f1c0024c368a','tenant-qualification','provider-qualification','qualification-session:0b5149fd055548519a9689b91a1477df',NULL,'xray-provider-qualification','open','{\"qualification\": true}',NULL,'2026-08-11 11:19:20','2026-08-11 11:19:20');
/*!40000 ALTER TABLE `xray_accuracy_session` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `xray_accuracy_session_event`
--

DROP TABLE IF EXISTS `xray_accuracy_session_event`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `xray_accuracy_session_event` (
  `id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(64)：Session event opaque 标识',
  `session_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(64)：所属 Session opaque 标识，不声明 foreign key',
  `tenant_id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(128)：租户标识，查询必须与 JWT 一致',
  `event_type` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(64)：Session 生命周期事件类型',
  `payload_hash` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'CHAR(64)：事件脱敏 payload SHA256，不保存敏感值',
  `trace_namespace` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(128)：Session 生命周期审计命名空间',
  `payload_json` json DEFAULT NULL COMMENT 'JSON：仅保存脱敏生命周期摘要',
  `created_by` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(128)：创建事件的认证主体 opaque 标识',
  `created_at` datetime NOT NULL DEFAULT (now()) COMMENT 'TIMESTAMP：记录创建时间（UTC），用于不可变审计',
  `updated_at` datetime NOT NULL DEFAULT (now()) COMMENT 'TIMESTAMP：记录更新时间（UTC），仅技术状态可更新',
  PRIMARY KEY (`id`),
  KEY `ix_xray_session_event_tenant_session` (`tenant_id`,`session_id`,`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `xray_accuracy_session_event`
--

LOCK TABLES `xray_accuracy_session_event` WRITE;
/*!40000 ALTER TABLE `xray_accuracy_session_event` DISABLE KEYS */;
INSERT INTO `xray_accuracy_session_event` VALUES ('1438dbcff2d54cf5a5ade35d79dcdd89','593f5fe0e0254cce999ac6148f6f9f93','tenant-qualification','session_started','d2541a86809f048073bbf8b9c1f71bd329b5c91965440a8771522cfcdb86be1a','xray.session:593f5fe0e0254cce999ac6148f6f9f93','{\"module_key\": \"xray-provider-qualification\", \"case_request_id_present\": false}','provider-qualification','2026-08-11 11:15:25','2026-08-11 11:15:25'),('1709ee13b3af4e4bb1dedd8fe2070e6b','df7343d22b1e4e54b8b4ec44d0973720','tenant-qualification','session_started','d2541a86809f048073bbf8b9c1f71bd329b5c91965440a8771522cfcdb86be1a','xray.session:df7343d22b1e4e54b8b4ec44d0973720','{\"module_key\": \"xray-provider-qualification\", \"case_request_id_present\": false}','provider-qualification','2026-08-11 11:18:35','2026-08-11 11:18:35'),('46733041cd204b15b2f85815bb790185','c6908ebe329141b487fe7418d09ff644','tenant-qualification','session_started','d2541a86809f048073bbf8b9c1f71bd329b5c91965440a8771522cfcdb86be1a','xray.session:c6908ebe329141b487fe7418d09ff644','{\"module_key\": \"xray-provider-qualification\", \"case_request_id_present\": false}','provider-qualification','2026-08-11 11:17:48','2026-08-11 11:17:48'),('9bbfc245fa0f45dc91365f130ed8b67b','e5b71ffc99ed4d0ebfcc9f539184bc05','tenant-qualification','session_started','d2541a86809f048073bbf8b9c1f71bd329b5c91965440a8771522cfcdb86be1a','xray.session:e5b71ffc99ed4d0ebfcc9f539184bc05','{\"module_key\": \"xray-provider-qualification\", \"case_request_id_present\": false}','provider-qualification','2026-08-11 11:22:57','2026-08-11 11:22:57'),('d49d9ef162b34faa895425c538215b46','0c7504ea9fa2434a90284448d9390a18','tenant-qualification','session_started','d2541a86809f048073bbf8b9c1f71bd329b5c91965440a8771522cfcdb86be1a','xray.session:0c7504ea9fa2434a90284448d9390a18','{\"module_key\": \"xray-provider-qualification\", \"case_request_id_present\": false}','provider-qualification','2026-08-11 11:13:10','2026-08-11 11:13:10'),('e0ea5b0db78f4ea894b91f3c43d29367','f004b4b097594defa289f1c0024c368a','tenant-qualification','session_started','d2541a86809f048073bbf8b9c1f71bd329b5c91965440a8771522cfcdb86be1a','xray.session:f004b4b097594defa289f1c0024c368a','{\"module_key\": \"xray-provider-qualification\", \"case_request_id_present\": false}','provider-qualification','2026-08-11 11:19:20','2026-08-11 11:19:20');
/*!40000 ALTER TABLE `xray_accuracy_session_event` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `xray_accuracy_stage_checkpoint`
--

DROP TABLE IF EXISTS `xray_accuracy_stage_checkpoint`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `xray_accuracy_stage_checkpoint` (
  `id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(64)：StageCheckpoint 唯一标识',
  `run_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(64)：所属 Run opaque 标识，不声明 foreign key',
  `tenant_id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(128)：租户标识，禁止跨租户读取',
  `stage_key` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(64)：状态机节点白名单名称',
  `attempt_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(64)：逻辑任务尝试标识；Provider physical retry 由 ModelCall attempt_id 区分',
  `status` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(32)：阶段状态 queued/retry/running/completed/failed/cancelled/late',
  `owner_id` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'VARCHAR(128)：Worker lease 所有者，可为空',
  `expected_version` bigint NOT NULL COMMENT 'BIGINT：claim 时预期 Run state_version',
  `input_hash` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'CHAR(64)：阶段输入摘要 SHA256',
  `output_hash` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'CHAR(64)：阶段输出摘要 SHA256，零模型可为空',
  `lease_expires_at` datetime DEFAULT NULL COMMENT 'TIMESTAMP：Worker lease 到期时间（UTC）',
  `heartbeat_at` datetime DEFAULT NULL COMMENT 'TIMESTAMP：Worker heartbeat 时间（UTC）',
  `started_at` datetime DEFAULT NULL COMMENT 'TIMESTAMP：阶段开始时间（UTC）',
  `finished_at` datetime DEFAULT NULL COMMENT 'TIMESTAMP：阶段结束时间（UTC）',
  `error_class` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'VARCHAR(64)：技术错误分类，不映射 normal/abnormal',
  `created_at` datetime NOT NULL DEFAULT (now()) COMMENT 'TIMESTAMP：记录创建时间（UTC），用于不可变审计',
  `updated_at` datetime NOT NULL DEFAULT (now()) COMMENT 'TIMESTAMP：记录更新时间（UTC），仅技术状态可更新',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_xray_checkpoint_run_stage_attempt` (`run_id`,`stage_key`,`attempt_id`),
  KEY `ix_xray_checkpoint_tenant_lease` (`tenant_id`,`status`,`lease_expires_at`),
  KEY `ix_xray_checkpoint_lease` (`status`,`lease_expires_at`),
  KEY `ix_xray_checkpoint_tenant_run_stage` (`tenant_id`,`run_id`,`stage_key`,`attempt_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `xray_accuracy_stage_checkpoint`
--

LOCK TABLES `xray_accuracy_stage_checkpoint` WRITE;
/*!40000 ALTER TABLE `xray_accuracy_stage_checkpoint` DISABLE KEYS */;
INSERT INTO `xray_accuracy_stage_checkpoint` VALUES ('029b0f522ff243a68fc97c440f422f94','e850b4b444b244d9a11f1f0e03be78d4','tenant-qualification','request_gate','370d456185754eb0b71007219d315141','completed',NULL,0,NULL,NULL,NULL,NULL,'2026-08-11 03:17:48','2026-08-11 03:17:49',NULL,'2026-08-11 11:17:48','2026-08-11 11:17:48'),('397cd72be1d54a7891273389a34c865b','5036a26d91f447678f915a573ea816bd','tenant-qualification','request_gate','95b80c1babca436d8f58b261e697dc67','retry',NULL,0,NULL,NULL,NULL,NULL,'2026-08-11 03:19:25','2026-08-11 03:19:26','provider_auth','2026-08-11 11:19:20','2026-08-11 11:19:26'),('64753c96b4dd4b7e8723ebc685b0b141','68b6258e5f794cea85260a9abc0be482','tenant-schema-recheck','request_gate','f15d01ebacde4be9a9fb744f425aeaf5','completed',NULL,0,NULL,NULL,NULL,NULL,'2026-08-10 05:09:04','2026-08-10 05:09:04',NULL,'2026-08-10 13:09:04','2026-08-10 13:09:04'),('684be09c1777492482c66325aa5a1ca4','ce7e9a7f363f48499e512bc03c6b3712','tenant-qualification','request_gate','de0fb342c48a43a8b21de8c0527d80f8','queued',NULL,0,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'2026-08-11 11:17:29','2026-08-11 11:17:29'),('6e6b2d08b69242a98eb79a0cb54beba7','c199b1bb84e1487393df8af188c76a1e','tenant-qualification','request_gate','31323ddec9c54257a5de4454bd9c4a54','completed',NULL,0,NULL,NULL,NULL,NULL,'2026-08-11 03:18:35','2026-08-11 03:18:35',NULL,'2026-08-11 11:18:35','2026-08-11 11:18:35'),('70262190a0924f97b5c940c7ae6c7be1','16e2e68e3cb7491aba284e5087a43655','schema-smoke-tenant','request_gate','fc68e85e39f1477c97eaf8b0637336f3','completed',NULL,0,NULL,NULL,NULL,NULL,'2026-08-10 04:40:46','2026-08-10 04:40:46',NULL,'2026-08-10 12:40:45','2026-08-10 12:40:45'),('705db166b6e74d78a88a6c04f61ac2a8','2f1e56b85c7e48a68b71aabd3e918d5e','tenant-qualification','request_gate','5a6d87e4a67a462aadcfc9008c2b691d','retry',NULL,0,NULL,NULL,NULL,NULL,'2026-08-11 03:22:57','2026-08-11 03:22:58','provider_auth','2026-08-11 11:22:57','2026-08-11 11:22:58'),('83063e51871a47aab28183b0062ba45d','f38565fcab284c4bb26e424c09870f0f','tenant-qualification','request_gate','4efb9f07635c404a8fee1813fc2f6952','completed',NULL,0,NULL,NULL,NULL,NULL,'2026-08-11 03:19:20','2026-08-11 03:19:21',NULL,'2026-08-11 11:19:20','2026-08-11 11:19:20'),('8d8943d1af924db2987ebe0487101cbe','071bed59e733450bb4752fc3ee3ffd02','tenant-qualification','request_gate','395ca9ed57934d9381103069fbb53d9c','completed',NULL,0,NULL,NULL,NULL,NULL,'2026-08-11 03:15:25','2026-08-11 03:15:26',NULL,'2026-08-11 11:15:25','2026-08-11 11:15:26'),('e879b18489f74d1aa7c3380b519db311','f3e49dc1172a485a8192a201c9c02c35','tenant-qualification','request_gate','b30b1e5b326d48c7a03218ffeb8a4ef2','completed',NULL,0,NULL,NULL,NULL,NULL,'2026-08-11 03:22:57','2026-08-11 03:22:57',NULL,'2026-08-11 11:22:57','2026-08-11 11:22:57');
/*!40000 ALTER TABLE `xray_accuracy_stage_checkpoint` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `xray_accuracy_study_snapshot`
--

DROP TABLE IF EXISTS `xray_accuracy_study_snapshot`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `xray_accuracy_study_snapshot` (
  `id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(64)：Study snapshot 行 opaque 标识',
  `study_id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(128)：稳定 Study opaque 标识，不声明 foreign key',
  `study_revision_id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(128)：不可变 Study revision opaque 标识',
  `session_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(64)：所属 Session opaque 标识，不声明 foreign key',
  `tenant_id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(128)：租户标识，查询必须与 JWT 一致',
  `study_status` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(32)：Study 状态 received/assembling/ready_full_study/partial/over_budget/invalid/expired',
  `expected_image_count` int NOT NULL COMMENT 'INT：上游声明的 expected image 数量，不等于已发送数量',
  `expected_manifest_sha256` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'CHAR(64)：expected manifest ordered SHA256',
  `preparation_metadata_sha256` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'CHAR(64)：Study preparation 幂等输入摘要，不保存敏感元数据原文',
  `ordered_source_image_ids_json` json NOT NULL COMMENT 'JSON：按 source_index 排序的 opaque image asset 标识',
  `projection_groups_json` json DEFAULT NULL COMMENT 'JSON：投照分组及安全元数据，不作医学结论',
  `body_scope` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'VARCHAR(64)：检查部位安全提示，不含诊断结论',
  `species` varchar(32) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'VARCHAR(32)：物种安全元数据，未知时为空',
  `identity_confidence` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(32)：Study identity 置信状态 confirmed/conflict/unknown',
  `coverage_status` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(32)：覆盖状态 unknown/ready_for_request/full_sent/partial_sent/over_budget',
  `frozen_at` datetime DEFAULT NULL COMMENT 'TIMESTAMP：Study revision 冻结时间（UTC），非空后不可修改',
  `created_at` datetime NOT NULL DEFAULT (now()) COMMENT 'TIMESTAMP：记录创建时间（UTC），用于不可变审计',
  `updated_at` datetime NOT NULL DEFAULT (now()) COMMENT 'TIMESTAMP：记录更新时间（UTC），仅技术状态可更新',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_xray_study_revision` (`tenant_id`,`study_revision_id`),
  KEY `ix_xray_study_tenant_session` (`tenant_id`,`session_id`,`created_at`),
  KEY `ix_xray_study_tenant_status` (`tenant_id`,`study_status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `xray_accuracy_study_snapshot`
--

LOCK TABLES `xray_accuracy_study_snapshot` WRITE;
/*!40000 ALTER TABLE `xray_accuracy_study_snapshot` DISABLE KEYS */;
INSERT INTO `xray_accuracy_study_snapshot` VALUES ('07b8df3cbd0e4d60bfbc85e0ffe278a2','qualification-study:d3a7ad36501142fc85b910748c988aa9','958907665516068286d06f85562cb07e','df7343d22b1e4e54b8b4ec44d0973720','tenant-qualification','ready_full_study',2,'6068d62ca170f1d0ca91649d9a1f0b724c6ca64ba2b71c15ca5b013ab0b7e5d8','d86ac930445f1ba15f646fbc4c349b8a89d44c468cf74574dc0660f60abcad01','[\"1aa51013104e4195a5711c37c6d0e194\", \"5c4a27a4344e4617ab1ea33dfd954d0c\"]','[{\"body_part\": null, \"projection\": null, \"source_index\": 0}, {\"body_part\": null, \"projection\": null, \"source_index\": 1}]','qualification',NULL,'confirmed','ready_for_request','2026-08-11 03:18:35','2026-08-11 11:18:35','2026-08-11 11:18:35'),('192120ad5a494176a3315aec47789ad9','qualification-study:c1b34ab6465d4feab3c01e4653317d23','de755a8134f92bb19d3e4d0d05408bb8','593f5fe0e0254cce999ac6148f6f9f93','tenant-qualification','ready_full_study',2,'f9a8be96c023822feec222fc32776cd57d29a5daff6cd4c2db7ea74992725282','274c5dab83a3610da0846906922c8b0566ba478df9847c8005595f16c51833ba','[\"3d08c3a29db44f508e44bbe2b8b061a2\", \"8207d3c466584f4e8b5aa958ae45c267\"]','[{\"body_part\": null, \"projection\": null, \"source_index\": 0}, {\"body_part\": null, \"projection\": null, \"source_index\": 1}]','qualification',NULL,'confirmed','ready_for_request','2026-08-11 03:15:26','2026-08-11 11:15:25','2026-08-11 11:15:26'),('4ffd33cd52de44058a41afc9dac4a1dd','qualification-study:4f3648dc5e91425fa26a6ed601334bc4','89a37bf064279907c0f5c2b4c00ba4c5','e5b71ffc99ed4d0ebfcc9f539184bc05','tenant-qualification','ready_full_study',2,'77b72842e0faf996c58ff635769a7c7debbf55795c5f4da36a9e35f1598dad72','3ea9d910d1a7aca20480711a0ef27f4740abb815a4d16781e6988d3f4b398ccc','[\"3d714307ded0480caf4c2bf1dfdec114\", \"31b22830c55e4e279090fd9db4c88074\"]','[{\"body_part\": null, \"projection\": null, \"source_index\": 0}, {\"body_part\": null, \"projection\": null, \"source_index\": 1}]','qualification',NULL,'confirmed','ready_for_request','2026-08-11 03:22:57','2026-08-11 11:22:57','2026-08-11 11:22:57'),('cd38126aa6d94976bb769513bc453e12','qualification-study:0b5149fd055548519a9689b91a1477df','5dd1c37c4a03b16187d03f3aacab79bb','f004b4b097594defa289f1c0024c368a','tenant-qualification','ready_full_study',2,'b3d1ca52befb27a72dd86f08a9576b473ecea6095e824bbe0be0383a9c9f503a','ae8a94e90cc0d4274f26102d0b81d1f6d7e8cab12adaaf3f03a7858df3a5242d','[\"e9530fe3e4bd4ddc9cbcf54acd1cdf60\", \"7a095c11443d45a893894c68ac7172db\"]','[{\"body_part\": null, \"projection\": null, \"source_index\": 0}, {\"body_part\": null, \"projection\": null, \"source_index\": 1}]','qualification',NULL,'confirmed','ready_for_request','2026-08-11 03:19:21','2026-08-11 11:19:20','2026-08-11 11:19:20'),('f4eca38fa2ed47a9b41439f1ae1537f3','qualification-study:8ee60f42cd7c4492bf045cdb24dbd1b6','2f6cbe2e2e4be621e8f12f87cd9fb987','c6908ebe329141b487fe7418d09ff644','tenant-qualification','ready_full_study',2,'91f8726f0437a13fe98b125f05d9616dab429393ca5015e822fe27d3f5e4e40e','32f62a9840e36c2cee0024381ba2831059851c85831a61c7b590a5ac139aea89','[\"1218e60f43fb42c3b903fb072e65b85e\", \"382da4af838b420e9c04bac1c166a068\"]','[{\"body_part\": null, \"projection\": null, \"source_index\": 0}, {\"body_part\": null, \"projection\": null, \"source_index\": 1}]','qualification',NULL,'confirmed','ready_for_request','2026-08-11 03:17:49','2026-08-11 11:17:48','2026-08-11 11:17:48');
/*!40000 ALTER TABLE `xray_accuracy_study_snapshot` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `xray_accuracy_trace_event`
--

DROP TABLE IF EXISTS `xray_accuracy_trace_event`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `xray_accuracy_trace_event` (
  `id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(64)：TraceEvent 唯一标识（append-only）',
  `run_id` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(64)：所属 Run opaque 标识，不声明 foreign key',
  `tenant_id` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(128)：租户标识，读取必须 tenant filter',
  `trace_namespace` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(128)：跨 HTTP/Broker/Worker 的 trace namespace',
  `stage_key` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(64)：阶段节点白名单名称',
  `event_type` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'VARCHAR(64)：技术事件类型，不承载医学 verdict',
  `event_payload_json` json DEFAULT NULL COMMENT 'JSON：脱敏事件字段，不含 prompt/原图/secret',
  `fingerprint` varchar(128) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'VARCHAR(128)：事件指纹，供重放与审计',
  `state_version` bigint NOT NULL COMMENT 'BIGINT：事件对应 Run CAS 版本',
  `created_at` datetime NOT NULL DEFAULT (now()) COMMENT 'TIMESTAMP：记录创建时间（UTC），用于不可变审计',
  `updated_at` datetime NOT NULL DEFAULT (now()) COMMENT 'TIMESTAMP：记录更新时间（UTC），仅技术状态可更新',
  PRIMARY KEY (`id`),
  KEY `ix_xray_trace_run_created` (`run_id`,`created_at`),
  KEY `ix_xray_trace_tenant_run_created` (`tenant_id`,`run_id`,`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `xray_accuracy_trace_event`
--

LOCK TABLES `xray_accuracy_trace_event` WRITE;
/*!40000 ALTER TABLE `xray_accuracy_trace_event` DISABLE KEYS */;
INSERT INTO `xray_accuracy_trace_event` VALUES ('2b43ca2caa85429e8b3cd33dc89d9fb8','ce7e9a7f363f48499e512bc03c6b3712','tenant-qualification','xray.v2:ce7e9a7f363f48499e512bc03c6b3712','request_gate','run_accepted','{\"validation_only\": true}','cbc14413743f80a97e4699c0c50e4820',0,'2026-08-11 11:17:29','2026-08-11 11:17:29'),('3fc19bea3c1748bca25f73d2eec1f46d','2f1e56b85c7e48a68b71aabd3e918d5e','tenant-qualification','xray.v2:2f1e56b85c7e48a68b71aabd3e918d5e','request_gate','run_accepted','{\"validation_only\": true}','cbc14413743f80a97e4699c0c50e4820',0,'2026-08-11 11:22:57','2026-08-11 11:22:57'),('3ff8055caa6a48c493cc2be37158084a','f3e49dc1172a485a8192a201c9c02c35','tenant-qualification','xray.v2:f3e49dc1172a485a8192a201c9c02c35','request_gate','run_accepted','{\"validation_only\": true}','90e9abb856f4fef6042ea15dbbfcf2d6',0,'2026-08-11 11:22:57','2026-08-11 11:22:57'),('708562f210ad4b539302894c7ecc2544','5036a26d91f447678f915a573ea816bd','tenant-qualification','xray.v2:5036a26d91f447678f915a573ea816bd','request_gate','run_accepted','{\"validation_only\": true}','cbc14413743f80a97e4699c0c50e4820',0,'2026-08-11 11:19:20','2026-08-11 11:19:20'),('7ca8f312435c411188e69f3e760ffbfb','f38565fcab284c4bb26e424c09870f0f','tenant-qualification','xray.v2:f38565fcab284c4bb26e424c09870f0f','request_gate','run_accepted','{\"validation_only\": true}','90e9abb856f4fef6042ea15dbbfcf2d6',0,'2026-08-11 11:19:20','2026-08-11 11:19:20'),('7d357e9624d74870aae9411bf9e472db','071bed59e733450bb4752fc3ee3ffd02','tenant-qualification','xray.v2:071bed59e733450bb4752fc3ee3ffd02','request_gate','run_accepted','{\"validation_only\": true}','90e9abb856f4fef6042ea15dbbfcf2d6',0,'2026-08-11 11:15:25','2026-08-11 11:15:25'),('89d3e9e625c44a3a93856d2de18e7f50','16e2e68e3cb7491aba284e5087a43655','schema-smoke-tenant','xray.v2:16e2e68e3cb7491aba284e5087a43655','request_gate','run_accepted','{\"validation_only\": true}','4384de96a91b60bc8d6f4c1d36518305',0,'2026-08-10 12:40:45','2026-08-10 12:40:45'),('8de80d4b415a4d5aa4f5b17f1888556b','c199b1bb84e1487393df8af188c76a1e','tenant-qualification','xray.v2:c199b1bb84e1487393df8af188c76a1e','request_gate','run_accepted','{\"validation_only\": true}','90e9abb856f4fef6042ea15dbbfcf2d6',0,'2026-08-11 11:18:35','2026-08-11 11:18:35'),('95a4a7409e2c40638d3e38c8a0d37415','e850b4b444b244d9a11f1f0e03be78d4','tenant-qualification','xray.v2:e850b4b444b244d9a11f1f0e03be78d4','request_gate','run_accepted','{\"validation_only\": true}','90e9abb856f4fef6042ea15dbbfcf2d6',0,'2026-08-11 11:17:48','2026-08-11 11:17:48'),('c0b69e32dd9d471986ea9e654822fda0','68b6258e5f794cea85260a9abc0be482','tenant-schema-recheck','xray.v2:68b6258e5f794cea85260a9abc0be482','request_gate','run_accepted','{\"validation_only\": true}','4384de96a91b60bc8d6f4c1d36518305',0,'2026-08-10 13:09:04','2026-08-10 13:09:04'),('trace-f15d01ebacde4be9a9fb744f425aeaf5','68b6258e5f794cea85260a9abc0be482','tenant-schema-recheck','xray.v2:68b6258e5f794cea85260a9abc0be482','request_gate','technical_ai_request_completed','{\"provider_key\": \"stub/replay\", \"model_call_recorded\": true, \"medical_verdict_produced\": false}','4384de96a91b60bc8d6f4c1d36518305',1,'2026-08-10 13:09:04','2026-08-10 13:09:04'),('trace-failure-5a6d87e4a67a462aadcfc9008c2b691d','2f1e56b85c7e48a68b71aabd3e918d5e','tenant-qualification','xray.v2:2f1e56b85c7e48a68b71aabd3e918d5e','request_gate','technical_ai_request_retry','{\"retryable\": true, \"error_class\": \"provider_auth\", \"medical_verdict_produced\": false}','cbc14413743f80a97e4699c0c50e4820',0,'2026-08-11 11:22:58','2026-08-11 11:22:58'),('trace-failure-95b80c1babca436d8f58b261e697dc67','5036a26d91f447678f915a573ea816bd','tenant-qualification','xray.v2:5036a26d91f447678f915a573ea816bd','request_gate','technical_ai_request_retry','{\"retryable\": true, \"error_class\": \"provider_auth\", \"medical_verdict_produced\": false}','cbc14413743f80a97e4699c0c50e4820',0,'2026-08-11 11:19:23','2026-08-11 11:19:23'),('trace-fc68e85e39f1477c97eaf8b0637336f3','16e2e68e3cb7491aba284e5087a43655','schema-smoke-tenant','xray.v2:16e2e68e3cb7491aba284e5087a43655','request_gate','technical_ai_request_completed','{\"provider_key\": \"stub/replay\", \"model_call_recorded\": true, \"medical_verdict_produced\": false}','4384de96a91b60bc8d6f4c1d36518305',1,'2026-08-10 12:40:45','2026-08-10 12:40:45'),('trace-study-preparation-31323ddec9c54257a5de4454bd9c4a54','c199b1bb84e1487393df8af188c76a1e','tenant-qualification','xray.v2:c199b1bb84e1487393df8af188c76a1e','request_gate','technical_study_preparation_completed','{\"image_count\": 2, \"coverage_status\": \"ready_for_request\", \"study_revision_id\": \"958907665516068286d06f85562cb07e\", \"medical_verdict_produced\": false}','90e9abb856f4fef6042ea15dbbfcf2d6',1,'2026-08-11 11:18:35','2026-08-11 11:18:35'),('trace-study-preparation-370d456185754eb0b71007219d315141','e850b4b444b244d9a11f1f0e03be78d4','tenant-qualification','xray.v2:e850b4b444b244d9a11f1f0e03be78d4','request_gate','technical_study_preparation_completed','{\"image_count\": 2, \"coverage_status\": \"ready_for_request\", \"study_revision_id\": \"2f6cbe2e2e4be621e8f12f87cd9fb987\", \"medical_verdict_produced\": false}','90e9abb856f4fef6042ea15dbbfcf2d6',1,'2026-08-11 11:17:48','2026-08-11 11:17:48'),('trace-study-preparation-395ca9ed57934d9381103069fbb53d9c','071bed59e733450bb4752fc3ee3ffd02','tenant-qualification','xray.v2:071bed59e733450bb4752fc3ee3ffd02','request_gate','technical_study_preparation_completed','{\"image_count\": 2, \"coverage_status\": \"ready_for_request\", \"study_revision_id\": \"de755a8134f92bb19d3e4d0d05408bb8\", \"medical_verdict_produced\": false}','90e9abb856f4fef6042ea15dbbfcf2d6',1,'2026-08-11 11:15:26','2026-08-11 11:15:26'),('trace-study-preparation-4efb9f07635c404a8fee1813fc2f6952','f38565fcab284c4bb26e424c09870f0f','tenant-qualification','xray.v2:f38565fcab284c4bb26e424c09870f0f','request_gate','technical_study_preparation_completed','{\"image_count\": 2, \"coverage_status\": \"ready_for_request\", \"study_revision_id\": \"5dd1c37c4a03b16187d03f3aacab79bb\", \"medical_verdict_produced\": false}','90e9abb856f4fef6042ea15dbbfcf2d6',1,'2026-08-11 11:19:20','2026-08-11 11:19:20'),('trace-study-preparation-b30b1e5b326d48c7a03218ffeb8a4ef2','f3e49dc1172a485a8192a201c9c02c35','tenant-qualification','xray.v2:f3e49dc1172a485a8192a201c9c02c35','request_gate','technical_study_preparation_completed','{\"image_count\": 2, \"coverage_status\": \"ready_for_request\", \"study_revision_id\": \"89a37bf064279907c0f5c2b4c00ba4c5\", \"medical_verdict_produced\": false}','90e9abb856f4fef6042ea15dbbfcf2d6',1,'2026-08-11 11:22:57','2026-08-11 11:22:57');
/*!40000 ALTER TABLE `xray_accuracy_trace_event` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Dumping events for database 'ms_image_imaging_test'
--

--
-- Dumping routines for database 'ms_image_imaging_test'
--
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-08-11 12:05:40
