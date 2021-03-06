<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0">

    <!-- **********************************************************************
         Inventory Warehouse - CSV Import Stylesheet

         1st May 2011 / Graeme Foster <graeme AT acm DOT org>

         - use for import to /inv/warehouse/create resource
         - example raw URL usage:
           Let URLpath be the URL to Sahana Eden appliation
           Let Resource be inv/warehouse/create
           Let Type be s3csv
           Let CSVPath be the path on the server to the CSV file to be imported
           Let XSLPath be the path on the server to the XSL transform file
           Then in the browser type:

           URLpath/Resource.Type?filename=CSVPath&transform=XSLPath

           You can add a third argument &ignore_errors

         CSV fields:
         Warehouse..............org_office
         Category...............supply_item_category
         Item description.......supply_item.name
         Catalogue number.......supply_catalog.name
         Tracking number (CTN)..
         Remark.................
         Outbound...............
         UM.....................supply_item.um
         Currency...............
         Price..................
         Stock..................
         Price..................
         Stock..................inv_inv_item.quantity
         Price..................
         Stock..................

    *********************************************************************** -->
    <xsl:output method="xml"/>

    <xsl:key name="warehouse" match="row" use="col[@field='Warehouse']"/>
    <xsl:key name="item_category" match="row" use="col[@field='Category']"/>
    <xsl:key name="supply_item" match="row" use="col[@field='Item description']"/>

    <!-- ****************************************************************** -->

    <xsl:template match="/">
        <s3xml>

            <!-- Warehouses -->
            <xsl:for-each select="//row[generate-id(.)=generate-id(key('warehouse', col[@field='Warehouse'])[1])]">
                <xsl:call-template name="Warehouse"/>
            </xsl:for-each>

            <!-- Item Categories -->
            <xsl:for-each select="//row[generate-id(.)=generate-id(key('item_category', col[@field='Category'])[1])]">
                <xsl:call-template name="ItemCategory"/>
            </xsl:for-each>

            <!-- Catalog Items -->
            <xsl:for-each select="//row[generate-id(.)=generate-id(key('supply_item', col[@field='Item description'])[1])]">
                <xsl:call-template name="SupplyItem"/>
            </xsl:for-each>

            <!-- Inventory Items -->
            <xsl:apply-templates select="table/row"/>

        </s3xml>
    </xsl:template>

    <!-- ****************************************************************** -->
    <xsl:template match="row">

        <xsl:variable name="item" select="col[@field='Item description']/text()"/>
        <xsl:variable name="warehouse" select="col[@field='Warehouse']/text()"/>

        <resource name="inv_inv_item">
            <!-- Link to Supply Item -->
            <reference field="item_id" resource="supply_item">
                <xsl:attribute name="tuid">
                    <xsl:value-of select="$item"/>
                </xsl:attribute>
            </reference>
            <!-- Link to Warehouse -->
            <reference field="site_id" resource="org_office">
                <xsl:attribute name="tuid">
                    <xsl:value-of select="$warehouse"/>
                </xsl:attribute>
            </reference>
            <data field="quantity"><xsl:value-of select="col[@field='Stock']/text()"/></data>
            <data field="comments"><xsl:value-of select="col[@field='Remark']/text()"/></data>
        </resource>

    </xsl:template>

    <!-- ****************************************************************** -->
    <xsl:template name="Warehouse">
        <xsl:variable name="warehouse" select="col[@field='Warehouse']/text()"/>

        <resource name="org_office">
            <xsl:attribute name="tuid">
                <xsl:value-of select="$warehouse"/>
            </xsl:attribute>
            <data field="name"><xsl:value-of select="$warehouse"/></data>
            <data field="type">5</data>
        </resource>

    </xsl:template>

    <!-- ****************************************************************** -->
    <xsl:template name="ItemCategory">
        <xsl:variable name="category" select="col[@field='Category']/text()"/>

        <resource name="supply_item_category">
            <xsl:attribute name="tuid">
                <xsl:value-of select="$category"/>
            </xsl:attribute>
            <data field="code"><xsl:value-of select="$category"/></data>
        </resource>

    </xsl:template>

    <!-- ****************************************************************** -->
    <xsl:template name="SupplyItem">
        <xsl:variable name="item" select="col[@field='Item description']/text()"/>
        <xsl:variable name="category" select="col[@field='Category']/text()"/>

        <resource name="supply_item">
            <xsl:attribute name="tuid">
                <xsl:value-of select="$item"/>
            </xsl:attribute>
            <data field="name"><xsl:value-of select="$item"/></data>
            <data field="um"><xsl:value-of select="col[@field='UM']/text()"/></data>
            <!-- Link to Supply Item Category -->
            <reference field="item_category_id" resource="supply_item_category">
                <xsl:attribute name="tuid">
                    <xsl:value-of select="$category"/>
                </xsl:attribute>
            </reference>
        </resource>

    </xsl:template>

    <!-- ****************************************************************** -->

</xsl:stylesheet>
