-- =====================================================
-- MySQL Cluster Test SQL Script
-- Execute this file to test the cluster
-- =====================================================

-- 1. Database and Table Creation
-- =====================================================
CREATE DATABASE IF NOT EXISTS kamo_test;
USE kamo_test;

CREATE TABLE IF NOT EXISTS mitou_members (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    age INT NOT NULL,
    role VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- 2. Data Insertion
-- =====================================================
INSERT INTO mitou_members (name, age, role) VALUES
('Yusuke Miyazaki', 23, 'B4'),
('Tatsuhiro Nakamori', 25, 'D1'),
('Tony Li', 24, 'M2');

-- =====================================================
-- 3. Data Confirmation
-- =====================================================
SELECT * FROM mitou_members;

-- =====================================================
-- 4. Replication Confirmation Test
-- =====================================================
-- Execute this query from other nodes via Router
-- and verify that the same data is visible.
SELECT COUNT(*) AS total_records FROM mitou_members;

-- =====================================================
-- 5. Transaction Confirmation
-- =====================================================
START TRANSACTION;
INSERT INTO mitou_members (name, age, role) VALUES ('Rika Shou', 22, 'B3');
COMMIT;

-- Verify after transaction
SELECT * FROM mitou_members;
SELECT COUNT(*) AS total_after_transaction FROM mitou_members;

-- =====================================================
-- 6. Node-to-Node Replication Check
-- =====================================================
-- Connect to each node via Router and verify the following:
SELECT @@server_id AS node_id, COUNT(*) AS record_count FROM kamo_test.mitou_members;

