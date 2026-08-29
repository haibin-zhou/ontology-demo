-- 商品中台【全量版】：与 ontology-demo 的 catalog.ttl 实例数据完全对齐
-- 在 L8 教学版基础上补了 certification（资质）、sku_certification（SKU-资质关联）、
-- promo_enrollment（促销报名）三张表，product 增加 status 列。
DROP TABLE IF EXISTS promo_enrollment;
DROP TABLE IF EXISTS sku_certification;
DROP TABLE IF EXISTS certification;
DROP TABLE IF EXISTS sku;
DROP TABLE IF EXISTS product;
DROP TABLE IF EXISTS brand_authorization;
DROP TABLE IF EXISTS merchant;
DROP TABLE IF EXISTS brand;
DROP TABLE IF EXISTS category;

CREATE TABLE category (
  id INT PRIMARY KEY,
  name VARCHAR(64) NOT NULL,
  parent_id INT REFERENCES category(id)
);

CREATE TABLE brand (
  id INT PRIMARY KEY,
  name VARCHAR(64) NOT NULL,
  country VARCHAR(32)
);

CREATE TABLE merchant (
  id INT PRIMARY KEY,
  name VARCHAR(64) NOT NULL
);

CREATE TABLE brand_authorization (
  id INT PRIMARY KEY,
  merchant_id INT NOT NULL REFERENCES merchant(id),
  brand_id INT NOT NULL REFERENCES brand(id),
  valid_until DATE NOT NULL
);

CREATE TABLE product (
  id INT PRIMARY KEY,
  name VARCHAR(64) NOT NULL,
  brand_id INT REFERENCES brand(id),
  status VARCHAR(16) NOT NULL          -- ACTIVE / DELISTED
);

CREATE TABLE sku (
  id INT PRIMARY KEY,
  product_id INT NOT NULL REFERENCES product(id),
  category_id INT REFERENCES category(id),
  merchant_id INT REFERENCES merchant(id),
  price DECIMAL(10,2) NOT NULL,
  sales_30d INT NOT NULL,
  inventory_days INT NOT NULL,
  min_price_30d DECIMAL(10,2),
  listed_date DATE NOT NULL
);

CREATE TABLE certification (
  id INT PRIMARY KEY,
  cert_type VARCHAR(32) NOT NULL,
  valid_until DATE NOT NULL
);

CREATE TABLE sku_certification (
  sku_id INT NOT NULL REFERENCES sku(id),
  cert_id INT NOT NULL REFERENCES certification(id),
  PRIMARY KEY (sku_id, cert_id)
);

CREATE TABLE promo_enrollment (
  id INT PRIMARY KEY,
  campaign VARCHAR(32) NOT NULL,
  sku_id INT NOT NULL REFERENCES sku(id),
  promo_price DECIMAL(10,2) NOT NULL
);
